import json
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import waiter_required
from menu.models import Category, Product

from . import services
from .models import ACTIVE_STATUSES, Order
from .payloads import order_payload
from .services import OrderError, can_edit


def _body(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or b"{}")
        except ValueError:
            raise OrderError("Noto‘g‘ri so‘rov.")
    return request.POST


def api(view):
    """JSON endpoint: login, POST, xatolarni JSON ga o'giradi."""

    @wraps(view)
    @require_POST
    @waiter_required
    def wrapper(request, pk, *args, **kwargs):
        try:
            services_result = view(request, pk, _body(request), *args, **kwargs)
        except PermissionDenied:
            return JsonResponse({"ok": False, "error": "Bu buyurtmani o‘zgartirishga ruxsat yo‘q."}, status=403)
        except OrderError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        order = get_object_or_404(Order.objects.select_related("table__section").prefetch_related("items"), pk=pk)
        payload = {"ok": True, "order": order_payload(order, request.user)}
        if isinstance(services_result, dict):
            payload.update(services_result)
        return JsonResponse(payload)

    return wrapper


@waiter_required
@require_POST
def open_table(request, table_id):
    try:
        order, _created = services.open_order_for_table(table_id, request.user)
    except OrderError as exc:
        messages.error(request, str(exc))
        return redirect("sectors")
    if not can_edit(request.user, order):
        messages.error(request, f"Bu joy {order.waiter.display_name} ofitsiantga biriktirilgan.")
        return redirect("sector_detail", pk=order.table.section_id)
    return redirect("order_detail", pk=order.pk)


@waiter_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("table__section", "waiter").prefetch_related("items"), pk=pk)
    if not can_edit(request.user, order):
        raise PermissionDenied
    categories = Category.objects.filter(active=True).prefetch_related(
        Prefetch("products", queryset=Product.objects.filter(available=True).order_by("sort_order", "name"))
    )
    categories = [c for c in categories if c.products.all()]
    return render(
        request,
        "orders/order_detail.html",
        {"order": order, "categories": categories, "payload": order_payload(order, request.user)},
    )


@api
def add_item(request, pk, data):
    services.add_item(pk, request.user, data.get("product_id"), data.get("quantity", 1), data.get("note", ""))


@api
def set_quantity(request, pk, data, item_id):
    services.set_item_quantity(pk, request.user, item_id, data.get("quantity"), data.get("delta"))


@api
def remove_item(request, pk, data, item_id):
    services.remove_item(pk, request.user, item_id)


@api
def set_note(request, pk, data, item_id):
    services.set_item_note(pk, request.user, item_id, data.get("note", ""))


@api
def send_order(request, pk, data):
    services.send_order(pk, request.user)


@api
def request_payment(request, pk, data):
    services.request_payment(pk, request.user)


@api
def cancel_order(request, pk, data):
    services.cancel_order(pk, request.user)
    return {"redirect": "/sectors/"}


@waiter_required
def my_orders(request):
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    orders = (
        Order.objects.filter(waiter=request.user, created_at__gte=start)
        .select_related("table__section")
        .prefetch_related("items")
    )
    active = [o for o in orders if o.status in ACTIVE_STATUSES]
    closed = [o for o in orders if o.status not in ACTIVE_STATUSES]
    return render(request, "orders/my_orders.html", {"active": active, "closed": closed})
