from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Naqd"
        CARD = "card", "Karta"
        TRANSFER = "transfer", "O‘tkazma"

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments", verbose_name="Buyurtma")
    amount = models.PositiveIntegerField("Summa (so‘m)")
    method = models.CharField("Usul", max_length=10, choices=Method.choices, default=Method.CASH)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_payments"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "To‘lov"
        verbose_name_plural = "To‘lovlar"

    def __str__(self):
        return f"#{self.order_id} — {self.amount} ({self.get_method_display()})"
