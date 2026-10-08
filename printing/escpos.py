"""ESC/POS ticket rendering. Hech qanday tashqi kutubxona kerak emas."""
import textwrap

from django.conf import settings
from django.utils import timezone

ESC = b"\x1b"
GS = b"\x1d"
INIT = ESC + b"@"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
DOUBLE_ON = GS + b"!\x11"
DOUBLE_OFF = GS + b"!\x00"
FEED_AND_CUT = ESC + b"d\x04" + GS + b"V\x42\x00"

_TRANSLATE = {
    0x2018: "'", 0x2019: "'", 0x02BB: "'", 0x02BC: "'", 0x0060: "'",
    0x2013: "-", 0x2014: "-", 0x00D7: "x", 0x2116: "N",
}


def to_ascii(text):
    return text.translate(_TRANSLATE).encode("ascii", "replace").decode("ascii")


def _width():
    return max(24, int(getattr(settings, "PRINT_WIDTH", 32)))


def render_ticket_text(order, station, items):
    """Bo'lim uchun chek matnini (Unicode) qaytaradi. Faqat shu bo'limning mahsulotlari."""
    width = _width()
    double = "=" * width
    single = "-" * width
    sent = [i.sent_at for i in items if i.sent_at]
    moment = timezone.localtime(max(sent) if sent else timezone.now())
    lines = [
        double,
        settings.RESTAURANT_NAME.center(width).rstrip(),
        double,
        "",
        f"Buyurtma: #{order.pk}",
        f"Sektor: {order.table.section.name.upper()}",
        f"Joy: {order.table.name}",
    ]
    if station is not None:
        lines.append(f"Bo'lim: {station.name.upper()}")
    lines += [
        f"Ofitsiant: {order.waiter.display_name}",
        f"Vaqt: {moment:%H:%M}",
        "",
        single,
        "",
    ]
    qty_w = 5
    for item in items:
        wrapped = textwrap.wrap(item.product_name, width - qty_w) or [""]
        lines.append(f"{wrapped[0]:<{width - qty_w}}{item.quantity:>{qty_w}}")
        lines.extend(wrapped[1:])
    lines += ["", single]
    noted = [i for i in items if i.note]
    notes = []
    if order.note:
        notes.append(order.note)
    if len(noted) == 1 and not order.note:
        notes.append(noted[0].note)
    else:
        notes.extend(f"{i.product_name}: {i.note}" for i in noted)
    if notes:
        lines += ["", "Izoh:"]
        for note in notes:
            lines.extend(textwrap.wrap(note, width) or [note])
    lines += ["", double]
    return "\n".join(lines)


def build_escpos(text):
    """Chek matnidan ESC/POS baytlarini yasaydi (sarlavha qalin va katta)."""
    ascii_lines = to_ascii(text).split("\n")
    out = bytearray(INIT)
    for index, line in enumerate(ascii_lines):
        if index == 1:
            out += ALIGN_CENTER + BOLD_ON + DOUBLE_ON + line.strip().encode("ascii") + b"\n" + DOUBLE_OFF + BOLD_OFF + ALIGN_LEFT
        else:
            out += line.encode("ascii", "replace") + b"\n"
    out += FEED_AND_CUT
    return bytes(out)
