from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Qassob Shashlik — Administrator"
admin.site.site_title = "Qassob Shashlik CRM"
admin.site.index_title = "Boshqaruv paneli"

handler403 = "config.views.permission_denied"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("locations.urls")),
    path("", include("orders.urls")),
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
