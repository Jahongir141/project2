"""Buyurtma biznes logikasi. Barcha o'zgarishlar tranzaksiya va qator qulfi (select_for_update) ichida."""
import logging
from functools import partial

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from locations.models import DiningTable
from menu.models import Product
from payments.models import Payment

from .models import ACTIVE_STATUSES, Order, OrderItem


class OrderError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato matni."""


def can_edit(user, order):
    return bool(user.is_active and (user.is_admin_role or order.waiter_id == user.id))


def _locked_order(order_id):
    try:
        return Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise OrderError("Buyurtma topilmadi.")


def _editable_order(order_id, user):
    order = _locked_order(order_id)
    if not can_edit(user, order):
        raise PermissionDenied
    if order.status not in ACTIVE_STATUSES:
        raise OrderError("Buyurtma yopilgan, o‘zgartirib bo‘lmaydi.")
    return order


def _new_item(order, item_id):
    try:
        item = OrderItem.objects.select_for_update().get(pk=item_id, order=order)
    except OrderItem.DoesNotExist:
        raise OrderError("Mahsulot topilmadi.")
    if item.status != OrderItem.Status.NEW:
        raise OrderError("Yuborilgan mahsulotni o‘zgartirib bo‘lmaydi.")
    return item


def _clean_qty(quantity):
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise OrderError("Miqdor noto‘g‘ri.")
    if quantity < 1 or quantity > 99:
        raise OrderError("Miqdor 1 dan 99 gacha bo‘lishi kerak.")
    return quantity


# ---------- Order ochish ----------

def open_order_for_table(table_id, waiter):
    """Joy uchun faol buyurtmani qaytaradi yoki yangisini ochadi. Race-condition'ga chidamli."""
    with transaction.atomic():
        try:
            table = DiningTable.objects.select_for_update(of=("self",)).select_related("section").get(pk=table_id)
        except DiningTable.DoesNotExist:
            raise OrderError("Joy topilmadi.")
        existing = Order.objects.active().filter(table=table).first()
        if existing:
            return existing, False
        if not (table.active and table.section.active):
            raise OrderError("Bu joy hozir faol emas.")
        if not waiter.is_active:
            raise OrderError("Hisob faol emas.")
        try:
            with transaction.atomic():
                return Order.objects.create(table=table, waiter=waiter), True
        except IntegrityError:
            existing = Order.objects.active().filter(table=table).first()
            if existing:
                return existing, False
            raise


# ---------- Mahsulotlar ----------

def add_item(order_id, user, product_id, quantity=1, note=""):
    quantity = _clean_qty(quantity)
    note = (note or "").strip()[:255]
    with transaction.atomic():
        order = _editable_order(order_id, user)
        try:
            product = Product.objects.select_related("category", "preparation_station").get(pk=product_id)
        except Product.DoesNotExist:
            raise OrderError("Mahsulot topilmadi.")
        if not product.is_orderable:
            raise OrderError(f"«{product.name}» hozir mavjud emas.")
        if order.payment_requested:
            order.payment_requested = False
            order.save(update_fields=["payment_requested", "updated_at"])
        item = order.items.select_for_update().filter(
            product=product, status=OrderItem.Status.NEW, note=note, unit_price=product.price, product_name=product.name
        ).first()
        if item:
            item.quantity = min(99, item.quantity + quantity)
            item.save(update_fields=["quantity"])
        else:
            item = OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=quantity,
                note=note,
                station=product.preparation_station,
            )
        return item


def set_item_quantity(order_id, user, item_id, quantity=None, delta=None):
    try:
        quantity = None if quantity is None else int(quantity)
        delta = None if delta is None else int(delta)
    except (TypeError, ValueError):
        raise OrderError("Miqdor noto‘g‘ri.")
    if quantity is None and delta is None:
        raise OrderError("Miqdor ko‘rsatilmagan.")
    with transaction.atomic():
        order = _editable_order(order_id, user)
        item = _new_item(order, item_id)
        if delta is not None:
            quantity = min(99, item.quantity + delta)
        if quantity <= 0:
            item.delete()
            return None
        item.quantity = _clean_qty(quantity)
        item.save(update_fields=["quantity"])
        return item


def remove_item(order_id, user, item_id):
    with transaction.atomic():
        order = _editable_order(order_id, user)
        _new_item(order, item_id).delete()


def set_item_note(order_id, user, item_id, note):
    with transaction.atomic():
        order = _editable_order(order_id, user)
        item = _new_item(order, item_id)
        item.note = (note or "").strip()[:255]
        item.save(update_fields=["note"])
        return item


# ---------- Holat ----------

def recompute_status(order):
    items = [i for i in order.items.all() if i.status != OrderItem.Status.CANCELLED]
    sent = [i for i in items if i.status != OrderItem.Status.NEW]
    if not sent:
        new_status = Order.Status.OPEN
    elif all(i.status == OrderItem.Status.READY for i in sent):
        new_status = Order.Status.READY
    elif any(i.status in (OrderItem.Status.READY, OrderItem.Status.PREPARING) for i in sent):
        new_status = Order.Status.PARTIAL
    else:
        new_status = Order.Status.SENT
    if order.status in ACTIVE_STATUSES and order.status != new_status:
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
    return order


def _print_after_commit(order_id, item_ids):
    from printing.services import print_items

    try:
        order = Order.objects.select_related("table__section", "waiter").get(pk=order_id)
        items = list(OrderItem.objects.select_related("station").filter(pk__in=item_ids).order_by("id"))
        print_items(order, items)
    except Exception:  # chop etish xatosi buyurtmani buzmasligi kerak
        logging.getLogger("printing").exception("Chek yuborishda xatolik (buyurtma #%s)", order_id)


def send_order(order_id, user):
    """Yangi mahsulotlarni yuboradi. Ikki marta bosilsa ikkinchi chaqiruv rad etiladi."""
    with transaction.atomic():
        order = _editable_order(order_id, user)
        new_items = list(order.items.select_for_update().filter(status=OrderItem.Status.NEW))
        if not new_items:
            raise OrderError("Yuboriladigan yangi mahsulot yo‘q (buyurtma allaqachon yuborilgan).")
        now = timezone.now()
        ids = [i.pk for i in new_items]
        OrderItem.objects.filter(pk__in=ids).update(status=OrderItem.Status.SENT, sent_at=now)
        order.sent_at = order.sent_at or now
        order.payment_requested = False
        order.save(update_fields=["sent_at", "payment_requested", "updated_at"])
        recompute_status(order)
        transaction.on_commit(partial(_print_after_commit, order.pk, ids), robust=True)
        return order


def mark_items(order_id, status):
    """Admin: buyurtmaning yuborilgan mahsulotlarini PREPARING/READY holatiga o'tkazadi."""
    with transaction.atomic():
        order = _locked_order(order_id)
        order.items.filter(status__in=[OrderItem.Status.SENT, OrderItem.Status.PREPARING]).update(status=status)
        recompute_status(order)
        return order


def request_payment(order_id, user):
    with transaction.atomic():
        order = _editable_order(order_id, user)
        if not order.items.exclude(status__in=[OrderItem.Status.NEW, OrderItem.Status.CANCELLED]).exists():
            raise OrderError("Avval buyurtmani yuboring.")
        order.payment_requested = True
        order.save(update_fields=["payment_requested", "updated_at"])
        return order


def cancel_order(order_id, user):
    with transaction.atomic():
        order = _editable_order(order_id, user)
        has_sent = order.items.exclude(status__in=[OrderItem.Status.NEW, OrderItem.Status.CANCELLED]).exists()
        if has_sent and not user.is_admin_role:
            raise OrderError("Yuborilgan buyurtmani faqat administrator bekor qila oladi.")
        order.items.exclude(status=OrderItem.Status.CANCELLED).update(status=OrderItem.Status.CANCELLED)
        order.status = Order.Status.CANCELLED
        order.payment_requested = False
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "payment_requested", "closed_at", "updated_at"])
        return order


# ---------- To'lov ----------

def settle_if_paid(order_id):
    """To'lovlar yig'indisi jami summaga yetsa, buyurtmani PAID qiladi."""
    with transaction.atomic():
        order = _locked_order(order_id)
        if order.status not in ACTIVE_STATUSES:
            return order
        paid = order.payments.aggregate(s=Sum("amount"))["s"] or 0
        total = order.total
        if total > 0 and paid >= total:
            order.status = Order.Status.PAID
            order.payment_requested = False
            order.closed_at = timezone.now()
            order.save(update_fields=["status", "payment_requested", "closed_at", "updated_at"])
        return order


def pay_order(order_id, user, method=Payment.Method.CASH):
    if not user.is_admin_role:
        raise PermissionDenied
    if method not in Payment.Method.values:
        raise OrderError("To‘lov usuli noto‘g‘ri.")
    with transaction.atomic():
        order = _locked_order(order_id)
        if order.status not in ACTIVE_STATUSES:
            raise OrderError("Buyurtma allaqachon yopilgan.")
        if order.items.filter(status=OrderItem.Status.NEW).exists():
            raise OrderError("Yuborilmagan mahsulotlar bor. Avval yuboring yoki o‘chiring.")
        total = order.total
        if total <= 0:
            raise OrderError("Buyurtma summasi 0 — to‘lov qabul qilib bo‘lmaydi.")
        paid = order.payments.aggregate(s=Sum("amount"))["s"] or 0
        remaining = total - paid
        if remaining > 0:
            Payment.objects.create(order=order, amount=remaining, method=method, received_by=user)
        return settle_if_paid(order.pk)
