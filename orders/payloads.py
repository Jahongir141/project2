from .models import OrderItem
from .services import can_edit

STATUS_LABELS = dict(OrderItem.Status.choices)


def order_payload(order, user):
    items = list(order.items.all())
    live = [i for i in items if i.status != OrderItem.Status.CANCELLED]
    editable = order.is_active and can_edit(user, order)
    return {
        "id": order.pk,
        "label": order.table.label,
        "status": order.status,
        "status_label": order.get_status_display(),
        "active": order.is_active,
        "editable": editable,
        "payment_requested": order.payment_requested,
        "total": sum(i.line_total for i in live),
        "has_new": any(i.status == OrderItem.Status.NEW for i in live),
        "has_sent": any(i.status != OrderItem.Status.NEW for i in live),
        "items": [
            {
                "id": i.pk,
                "name": i.product_name,
                "qty": i.quantity,
                "price": i.unit_price,
                "line": i.line_total,
                "note": i.note,
                "status": i.status,
                "status_label": STATUS_LABELS.get(i.status, i.status),
                "editable": editable and i.status == OrderItem.Status.NEW,
            }
            for i in live
        ],
    }
