from django.urls import path

from . import views

urlpatterns = [
    path("table/<int:table_id>/open/", views.open_table, name="open_table"),
    path("order/<int:pk>/", views.order_detail, name="order_detail"),
    path("order/<int:pk>/add/", views.add_item, name="order_add"),
    path("order/<int:pk>/item/<int:item_id>/qty/", views.set_quantity, name="order_qty"),
    path("order/<int:pk>/item/<int:item_id>/remove/", views.remove_item, name="order_remove"),
    path("order/<int:pk>/item/<int:item_id>/note/", views.set_note, name="order_note"),
    path("order/<int:pk>/send/", views.send_order, name="order_send"),
    path("order/<int:pk>/request-payment/", views.request_payment, name="order_request_payment"),
    path("order/<int:pk>/cancel/", views.cancel_order, name="order_cancel"),
    path("orders/mine/", views.my_orders, name="my_orders"),
]
