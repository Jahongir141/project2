from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        WAITER = "waiter", "Ofitsiant"

    role = models.CharField("Rol", max_length=10, choices=Role.choices, default=Role.WAITER, db_index=True)
    phone = models.CharField("Telefon", max_length=20, blank=True)

    objects = UserManager()

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    @property
    def is_admin_role(self):
        return self.is_active and self.role == self.Role.ADMIN

    @property
    def is_waiter_role(self):
        return self.is_active and self.role == self.Role.WAITER

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        # Rol yagona manba: administrator = Django Admin'ga to'liq kirish, ofitsiant = hech qachon.
        is_admin = self.role == self.Role.ADMIN
        self.is_staff = is_admin
        self.is_superuser = is_admin
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name
