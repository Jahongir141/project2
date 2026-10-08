from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from accounts.models import User
from orders import services
from orders.models import Order, OrderItem
from payments.models import Payment
from printing.models import PrintJob


def _today_start():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


@admin_required
def home(request):
    start = _today_start()
    month_start = start - timedelta(days=30)
    active = Order.objects.active()
    line_total = ExpressionWrapper(F("quantity") * F("unit_price"), output_field=IntegerField())
    context = {
        "orders_today": Order.objects.filter(created_at__gte=start).exclude(status=Order.Status.CANCELLED).count(),
        "revenue_today": Payment.objects.filter(created_at__gte=start).aggregate(s=Sum("amount"))["s"] or 0,
        "active_orders": active.count(),
        "busy_tables": active.order_by().values("table").distinct().count(),
        "waiters": User.objects.filter(role=User.Role.WAITER, is_active=True).annotate(
            today_orders=Count("orders", filter=Q(orders__created_at__gte=start), distinct=True),
            active_now=Count("orders", filter=Q(orders__status__in=["OPEN", "SENT", "PARTIAL", "READY"]), distinct=True),
        ).order_by("first_name", "username"),
        "top_products": OrderItem.objects.filter(created_at__gte=month_start)
        .exclude(status__in=[OrderItem.Status.NEW, OrderItem.Status.CANCELLED])
        .exclude(order__status=Order.Status.CANCELLED)
        .values("product_name")
        .annotate(qty=Sum("quantity"), revenue=Sum(line_total))
        .order_by("-qty")[:5],
    }
    return render(request, "dashboard/home.html", context)


@admin_required
def orders_list(request):
    active = (
        Order.objects.active()
        .select_related("table__section", "waiter")
        .prefetch_related("items")
        .order_by("created_at")
    )
    recent = (
        Order.objects.exclude(status__in=["OPEN", "SENT", "PARTIAL", "READY"])
        .select_related("table__section", "waiter")
        .prefetch_related("items")[:15]
    )
    return render(
        request,
        "dashboard/orders.html",
        {"active": active, "recent": recent, "methods": Payment.Method.choices},
    )


@admin_required
@require_POST
def order_action(request, pk, action):
    get_object_or_404(Order, pk=pk)
    try:
        if action == "ready":
            services.mark_items(pk, OrderItem.Status.READY)
            messages.success(request, f"Buyurtma #{pk}: hammasi tayyor.")
        elif action == "pay":
            services.pay_order(pk, request.user, request.POST.get("method", Payment.Method.CASH))
            messages.success(request, f"Buyurtma #{pk}: to‘lov qabul qilindi.")
        elif action == "cancel":
            services.cancel_order(pk, request.user)
            messages.success(request, f"Buyurtma #{pk} bekor qilindi.")
        else:
            raise PermissionDenied
    except services.OrderError as exc:
        messages.error(request, str(exc))
    return redirect("dashboard:orders")


@admin_required
def prints_list(request):
    jobs = PrintJob.objects.select_related("order", "station", "printer")[:50]
    return render(request, "dashboard/prints.html", {"jobs": jobs})


@admin_required
def print_detail(request, pk):
    job = get_object_or_404(PrintJob.objects.select_related("order", "station", "printer"), pk=pk)
    return render(request, "dashboard/print_detail.html", {"job": job})
