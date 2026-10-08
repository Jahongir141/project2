from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from .forms import UserCreateForm, UserEditForm
from .models import User


@admin.register(User)
class RestaurantUserAdmin(UserAdmin):
    form = UserEditForm
    add_form = UserCreateForm
    list_display = ("username", "first_name", "last_name", "role", "phone", "is_active", "last_login")
    list_filter = ("role", "is_active")
    search_fields = ("username", "first_name", "last_name", "phone")
    ordering = ("role", "username")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Shaxsiy ma’lumot", {"fields": ("first_name", "last_name", "phone", "email")}),
        ("Rol va holat", {"fields": ("role", "is_active")}),
        ("Sanalar", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )
    actions = ["deactivate_users", "activate_users"]

    @admin.action(description="Tanlanganlarni deaktivatsiya qilish")
    def deactivate_users(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)
        for user in queryset:
            user.is_active = False
            user.save()
        self.message_user(request, f"{queryset.count()} ta foydalanuvchi deaktivatsiya qilindi.", messages.SUCCESS)

    @admin.action(description="Tanlanganlarni faollashtirish")
    def activate_users(self, request, queryset):
        for user in queryset:
            user.is_active = True
            user.save()
        self.message_user(request, "Tanlangan foydalanuvchilar faollashtirildi.", messages.SUCCESS)
