from django import forms
from django.contrib import admin

from .models import DiningTable, Section


class DiningTableInline(admin.TabularInline):
    model = DiningTable
    extra = 2
    fields = ("name", "capacity", "sort_order", "active")


class SectionAdminForm(forms.ModelForm):
    generate_count = forms.IntegerField(
        label="Avtomatik joy yaratish",
        required=False,
        min_value=0,
        max_value=300,
        help_text="Masalan 17 kiriting — 1, 2, ... 17 raqamli joylar avtomatik yaratiladi (mavjudlari tegilmaydi).",
    )

    class Meta:
        model = Section
        fields = "__all__"


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    form = SectionAdminForm
    list_display = ("name", "table_count", "sort_order", "active")
    list_editable = ("sort_order", "active")
    search_fields = ("name",)
    inlines = [DiningTableInline]

    @admin.display(description="Joylar soni")
    def table_count(self, obj):
        return obj.tables.filter(active=True).count()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        count = form.cleaned_data.get("generate_count")
        if count:
            section = form.instance
            existing = set(section.tables.values_list("name", flat=True))
            DiningTable.objects.bulk_create(
                [
                    DiningTable(section=section, name=str(i), sort_order=i)
                    for i in range(1, count + 1)
                    if str(i) not in existing
                ]
            )


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "capacity", "sort_order", "active")
    list_editable = ("capacity", "sort_order", "active")
    list_filter = ("section", "active")
    search_fields = ("name", "section__name")
