from django.core.validators import MinValueValidator
from django.db import models

from .validators import validate_image_size


class Category(models.Model):
    name = models.CharField("Nomi", max_length=60, unique=True)
    sort_order = models.PositiveIntegerField("Tartib", default=0)
    active = models.BooleanField("Faol", default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"

    def __str__(self):
        return self.name


class Product(models.Model):
    class Unit(models.TextChoices):
        PIECE = "dona", "dona"
        PORTION = "porsiya", "porsiya"
        KG = "kg", "kg"
        LITER = "litr", "litr"
        SLICE = "bo‘lak", "bo‘lak"

    name = models.CharField("Nomi", max_length=120)
    description = models.TextField("Tavsif", blank=True)
    image = models.ImageField("Rasm", upload_to="products/%Y/%m/", blank=True, validators=[validate_image_size])
    price = models.PositiveIntegerField("Narx (so‘m)", validators=[MinValueValidator(0)])
    unit = models.CharField("Birlik", max_length=12, choices=Unit.choices, default=Unit.PIECE)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", verbose_name="Kategoriya")
    preparation_station = models.ForeignKey(
        "printing.Station", on_delete=models.PROTECT, related_name="products", verbose_name="Tayyorlash bo‘limi"
    )
    available = models.BooleanField("Mavjud", default=True)
    sort_order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        ordering = ["category__sort_order", "sort_order", "name"]
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        indexes = [models.Index(fields=["category", "available", "sort_order"])]

    @property
    def is_orderable(self):
        return self.available and self.category.active

    def __str__(self):
        return self.name
