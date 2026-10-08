from django.db import models


class Station(models.Model):
    name = models.CharField("Nomi", max_length=60, unique=True)
    sort_order = models.PositiveIntegerField("Tartib", default=0)
    active = models.BooleanField("Faol", default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Tayyorlash bo‘limi"
        verbose_name_plural = "Tayyorlash bo‘limlari"

    def __str__(self):
        return self.name


class Printer(models.Model):
    name = models.CharField("Nomi", max_length=80)
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="printers", verbose_name="Bo‘lim")
    ip_address = models.GenericIPAddressField("IP manzil")
    port = models.PositiveIntegerField("Port", default=9100)
    active = models.BooleanField("Faol", default=True)

    class Meta:
        ordering = ["station__sort_order", "name"]
        verbose_name = "Printer"
        verbose_name_plural = "Printerlar"

    def __str__(self):
        return f"{self.name} ({self.ip_address}:{self.port})"


class PrintJob(models.Model):
    class Status(models.TextChoices):
        PREVIEW = "PREVIEW", "Ko‘rinish (chop etilmagan)"
        SENT = "SENT", "Printerga yuborildi"
        FAILED = "FAILED", "Xatolik"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="print_jobs")
    station = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True, related_name="print_jobs")
    printer = models.ForeignKey(Printer, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    content = models.TextField("Chek matni")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PREVIEW)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Chop etish vazifasi"
        verbose_name_plural = "Chop etish vazifalari"

    def __str__(self):
        return f"#{self.order_id} → {self.station or 'Umumiy'} [{self.status}]"
