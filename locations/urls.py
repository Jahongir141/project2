from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("sectors/", views.sectors, name="sectors"),
    path("sectors/<int:pk>/", views.sector_detail, name="sector_detail"),
]
