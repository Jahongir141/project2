from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

ACTIVE_STATUSES = ("OPEN", "SENT", "PARTIAL", "READY")


class OrderQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=ACTIVE_STATUSES)


class Order(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Ochiq"
        SENT = "SENT", "Yuborilgan"
        PARTIAL = "PARTIAL", "Qisman tayyor"
        READY = "READY", "Tayyor"
        PAID = "PAID", "To‘langan"
        CANCELLED = "CANCELLED", "Bekor qilingan"

    table = models.ForeignKey("locations.DiningTable", on_delete=models.PROTECT, related_name="orders", verbose_name="Joy")
    waiter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders", verbose_name="Ofitsiant")
    status = models.CharField("Holat", max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    payment_requested = models.BooleanField("Hisob so‘ralgan", default=False)
    note = models.TextField("Izoh", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Buyurtma"
        verbose_name_plural = "Buyurtmalar"
        constraints = [
            models.UniqueConstraint(
                fields=["table"],
                condition=Q(status__in=ACTIVE_STATUSES),
                name="uniq_active_order_per_table",
            ),
        ]
        indexes = [models.Index(fields=["table", "status"]), models.Index(fields=["waiter", "status"])]

    @property
    def number(self):
        return self.pk

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES

    @property
    def total(self):
        return sum(i.line_total for i in self.items.all() if i.status != OrderItem.Status.CANCELLED)

    @property
    def table_state(self):
        if not self.is_active:
            return "free"
        if self.payment_requested:
            return "pay"
        if self.status == self.Status.READY:
            return "ready"
        if self.status in (self.Status.SENT, self.Status.PARTIAL):
            return "sent"
        return "busy"

    def __str__(self):
        return f"Buyurtma #{self.pk}"


class OrderItem(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "Yangi"
        SENT = "SENT", "Yuborilgan"
        PREPARING = "PREPARING", "Tayyorlanmoqda"
        READY = "READY", "Tayyor"
        CANCELLED = "CANCELLED", "Bekor qilingan"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("menu.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items")
    # Narx va nom snapshoti: mahsulot keyin o'zgarsa ham eski buyurtma buzilmaydi.
    product_name = models.CharField("Mahsulot nomi", max_length=120)
    unit_price = models.PositiveIntegerField("Birlik narxi")
    quantity = models.PositiveSmallIntegerField("Miqdor", default=1, validators=[MinValueValidator(1), MaxValueValidator(99)])
    note = models.CharField("Izoh", max_length=255, blank=True)
    station = models.ForeignKey("printing.Station", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items")
    status = models.CharField("Holat", max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Buyurtma elementi"
        verbose_name_plural = "Buyurtma elementlari"
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=1), name="orderitem_quantity_gte_1")]
        indexes = [models.Index(fields=["order", "status"]), models.Index(fields=["station", "status"])]

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"
