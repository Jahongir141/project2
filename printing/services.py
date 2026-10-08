import logging
import socket
from collections import OrderedDict

from django.conf import settings

from .escpos import build_escpos, render_ticket_text
from .models import PrintJob

logger = logging.getLogger("printing")


def send_to_printer(printer, payload):
    with socket.create_connection((printer.ip_address, printer.port), timeout=settings.PRINT_TIMEOUT) as sock:
        sock.sendall(payload)


def print_items(order, items):
    """Mahsulotlarni bo'limlar bo'yicha ajratib, har bir bo'lim printeriga chek yuboradi.

    Hech qachon xato ko'tarmaydi: printer topilmasa yoki ishlamasa PrintJob sifatida
    chek ko'rinishi (preview) saqlanadi va buyurtma ishlashda davom etadi.
    """
    jobs = []
    try:
        groups = OrderedDict()
        for item in items:
            groups.setdefault(item.station_id, []).append(item)
        for _station_id, group in groups.items():
            station = group[0].station
            text = render_ticket_text(order, station, group)
            printers = list(station.printers.filter(active=True)) if station else []
            if settings.PRINT_MODE != "network" or not printers:
                jobs.append(PrintJob.objects.create(order=order, station=station, content=text, status=PrintJob.Status.PREVIEW))
                continue
            payload = build_escpos(text)
            for printer in printers:
                try:
                    send_to_printer(printer, payload)
                    jobs.append(PrintJob.objects.create(order=order, station=station, printer=printer, content=text, status=PrintJob.Status.SENT))
                except Exception as exc:  # printer o'chiq/tarmoq xatosi — tizim buzilmasin
                    logger.warning("Printer %s ga yuborib bo'lmadi: %s", printer, exc)
                    jobs.append(PrintJob.objects.create(order=order, station=station, printer=printer, content=text, status=PrintJob.Status.FAILED, error=str(exc)))
    except Exception:
        logger.exception("Chek tayyorlashda kutilmagan xatolik (buyurtma #%s)", order.pk)
    return jobs


def reprint(job):
    """Mavjud PrintJob ni qayta yuboradi (admin amali)."""
    if job.printer is None or settings.PRINT_MODE != "network":
        job.status = PrintJob.Status.PREVIEW
        job.save(update_fields=["status"])
        return job
    try:
        send_to_printer(job.printer, build_escpos(job.content))
        job.status, job.error = PrintJob.Status.SENT, ""
    except Exception as exc:
        job.status, job.error = PrintJob.Status.FAILED, str(exc)
    job.save(update_fields=["status", "error"])
    return job
