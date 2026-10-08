from django.contrib import admin, messages

from payments.models import Payment

from . import services
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "product_name", "unit_price", "quantity", "note", "station", "status")
    readonly_fields = ("product_name", "unit_price", "station")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = ("amount", "method", "received_by", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "table", "waiter", "status", "order_total", "created_at")
    list_filter = ("status", "table__section", "waiter")
    search_fields = ("id", "table__name", "waiter__username")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, PaymentInline]
    list_select_related = ("table__section", "waiter")

    @admin.display(description="Jami (so‘m)")
    def order_total(self, obj):
        return f"{obj.total:,}".replace(",", " ")

    def save_formset(self, request, form, formset, change):
        if formset.model is not OrderItem:
            return super().save_formset(request, form, formset, change)
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for inst in instances:
            if inst.pk is None and not inst.product_id:
                continue
            if inst.pk is None:
                inst.product_name = inst.product.name
                inst.unit_price = inst.product.price
                inst.station = inst.product.preparation_station
            inst.save()
        formset.save_m2m()


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_name", "quantity", "unit_price", "station", "status", "created_at")
    list_filter = ("status", "station")
    search_fields = ("product_name", "order__id")
    actions = ["mark_preparing", "mark_ready"]
    list_select_related = ("order", "station")

    def _mark(self, request, queryset, status):
        for order_id in set(queryset.values_list("order_id", flat=True)):
            services.mark_items(order_id, status)
        self.message_user(request, "Holat yangilandi.", messages.SUCCESS)

    @admin.action(description="Tayyorlanmoqda deb belgilash")
    def mark_preparing(self, request, queryset):
        self._mark(request, queryset, OrderItem.Status.PREPARING)

    @admin.action(description="Tayyor deb belgilash")
    def mark_ready(self, request, queryset):
        self._mark(request, queryset, OrderItem.Status.READY)
