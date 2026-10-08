from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "active")
    list_editable = ("sort_order", "active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumb", "name", "category", "preparation_station", "price", "unit", "available", "sort_order")
    list_display_links = ("thumb", "name")
    list_editable = ("price", "available", "sort_order")
    list_filter = ("category", "preparation_station", "available")
    search_fields = ("name", "description")
    readonly_fields = ("image_preview",)
    fields = (
        "name", "description", ("image", "image_preview"), ("price", "unit"),
        ("category", "preparation_station"), ("available", "sort_order"),
    )

    @admin.display(description="Rasm")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;width:40px;object-fit:cover;border-radius:6px">', obj.image.url)
        return "—"

    @admin.display(description="Ko‘rinish")
    def image_preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" style="max-height:140px;border-radius:8px">', obj.image.url)
        return "Rasm yuklanmagan"
