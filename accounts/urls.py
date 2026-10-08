from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.RestaurantLoginView.as_view(), name="login"),
    path("logout/", views.RestaurantLogoutView.as_view(), name="logout"),
]
