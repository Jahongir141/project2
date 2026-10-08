from django.contrib import admin

from orders.services import settle_if_paid

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "amount", "method", "received_by", "created_at")
    list_filter = ("method",)
    date_hierarchy = "created_at"
    readonly_fields = ("received_by",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)
        settle_if_paid(obj.order_id)
