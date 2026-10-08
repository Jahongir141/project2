from django.contrib import admin, messages

from .models import Printer, PrintJob, Station
from .services import reprint


class PrinterInline(admin.TabularInline):
    model = Printer
    extra = 0


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "active")
    list_editable = ("sort_order", "active")
    inlines = [PrinterInline]


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ("name", "station", "ip_address", "port", "active")
    list_editable = ("active",)
    list_filter = ("station", "active")


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "station", "printer", "status", "created_at")
    list_filter = ("status", "station")
    readonly_fields = ("order", "station", "printer", "content", "status", "error", "created_at")
    actions = ["reprint_jobs"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Qayta chop etish")
    def reprint_jobs(self, request, queryset):
        for job in queryset:
            reprint(job)
        self.message_user(request, "Qayta chop etish bajarildi.", messages.SUCCESS)
