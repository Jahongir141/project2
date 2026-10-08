from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("orders/", views.orders_list, name="orders"),
    path("orders/<int:pk>/<str:action>/", views.order_action, name="order_action"),
    path("prints/", views.prints_list, name="prints"),
    path("prints/<int:pk>/", views.print_detail, name="print_detail"),
]
