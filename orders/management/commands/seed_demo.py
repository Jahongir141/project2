from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from locations.models import DiningTable, Section
from menu.models import Category, Product
from printing.models import Printer, Station

SECTIONS = [("Zal", 17), ("Ko‘cha", 8), ("Tapchan", 10), ("Kabina", 5)]
PREFIX = {"Tapchan": "T", "Kabina": "K"}
STATIONS = [("Oshxona", "192.168.1.201"), ("Gril", "192.168.1.203"), ("Salat", "192.168.1.204"), ("Bar", "192.168.1.202")]
CATEGORIES = ["Shashlik", "Salatlar", "Sho‘rvalar", "Ichimliklar"]
PRODUCTS = [
    ("Shashlik", "Qo‘y shashlik", "Yumshoq qo‘y go‘shti, ko‘mirda", 25000, "dona", "Gril"),
    ("Shashlik", "Mol go‘shti shashlik", "Marinadlangan mol go‘shti", 22000, "dona", "Gril"),
    ("Shashlik", "Tovuq shashlik", "Tovuq filesi, maxsus sous", 18000, "dona", "Gril"),
    ("Shashlik", "Jigar shashlik", "Yangi jigar, piyoz bilan", 20000, "dona", "Gril"),
    ("Shashlik", "Lyulya kabob", "Qo‘y go‘shtidan", 20000, "dona", "Gril"),
    ("Salatlar", "Achchiq-chuchuk", "Pomidor va piyoz salati", 15000, "porsiya", "Salat"),
    ("Salatlar", "Svejiy salat", "Bodring, pomidor, ko‘kat", 14000, "porsiya", "Salat"),
    ("Sho‘rvalar", "Mastava", "Uy usulida", 22000, "porsiya", "Oshxona"),
    ("Sho‘rvalar", "Sho‘rva", "Qo‘y go‘shtli", 28000, "porsiya", "Oshxona"),
    ("Ichimliklar", "Suv", "0.5 l", 5000, "dona", "Bar"),
    ("Ichimliklar", "Coca-Cola", "0.5 l", 10000, "dona", "Bar"),
    ("Ichimliklar", "Choy", "Choynak", 8000, "dona", "Bar"),
]


class Command(BaseCommand):
    help = "Demo ma'lumotlarni yaratadi (idempotent): admin, ofitsiant, sektorlar, joylar, bo'limlar, menyu."

    @transaction.atomic
    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"first_name": "Administrator", "role": User.Role.ADMIN, "is_superuser": True},
        )
        if created:
            admin.set_password("admin12345")
            admin.save()
        waiter, created_w = User.objects.get_or_create(
            username="ofitsiant", defaults={"first_name": "Jahongir", "role": User.Role.WAITER}
        )
        if created_w:
            waiter.set_password("ofitsiant12345")
            waiter.save()

        for order_no, (name, count) in enumerate(SECTIONS, start=1):
            section, _ = Section.objects.get_or_create(name=name, defaults={"sort_order": order_no})
            prefix = PREFIX.get(name, "")
            for i in range(1, count + 1):
                DiningTable.objects.get_or_create(
                    section=section, name=f"{prefix}{i}", defaults={"sort_order": i, "capacity": 4}
                )

        stations = {}
        for order_no, (name, ip) in enumerate(STATIONS, start=1):
            station, _ = Station.objects.get_or_create(name=name, defaults={"sort_order": order_no})
            stations[name] = station
            Printer.objects.get_or_create(
                station=station, name=f"{name} printer", defaults={"ip_address": ip, "port": 9100}
            )

        categories = {}
        for order_no, name in enumerate(CATEGORIES, start=1):
            categories[name], _ = Category.objects.get_or_create(name=name, defaults={"sort_order": order_no})

        for order_no, (cat, name, desc, price, unit, station) in enumerate(PRODUCTS, start=1):
            Product.objects.get_or_create(
                name=name,
                category=categories[cat],
                defaults={
                    "description": desc, "price": price, "unit": unit,
                    "preparation_station": stations[station], "sort_order": order_no,
                },
            )

        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar tayyor."))
        self.stdout.write("Admin:     admin / admin12345   (faqat demo uchun — productionda almashtiring!)")
        self.stdout.write("Ofitsiant: ofitsiant / ofitsiant12345")
