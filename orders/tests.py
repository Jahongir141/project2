import json

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from locations.models import DiningTable, Section
from menu.models import Category, Product
from orders import services
from orders.models import Order, OrderItem
from orders.services import OrderError
from payments.models import Payment
from printing.models import PrintJob, Station
from printing.services import print_items


class BaseCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin1", password="pass12345", role=User.Role.ADMIN, first_name="Admin")
        cls.waiter = User.objects.create_user("w1", password="pass12345", first_name="Ali")
        cls.waiter2 = User.objects.create_user("w2", password="pass12345", first_name="Vali")
        cls.section = Section.objects.create(name="Zal", sort_order=1)
        cls.table = DiningTable.objects.create(section=cls.section, name="5", sort_order=5)
        cls.grill = Station.objects.create(name="Gril")
        cls.bar = Station.objects.create(name="Bar")
        cls.salad = Station.objects.create(name="Salat")
        cls.cat = Category.objects.create(name="Shashlik")
        cls.lamb = Product.objects.create(name="Qo‘y shashlik", price=25000, category=cls.cat, preparation_station=cls.grill)
        cls.water = Product.objects.create(name="Suv", price=5000, category=cls.cat, preparation_station=cls.bar)
        cls.spicy = Product.objects.create(name="Achchiq-chuchuk", price=15000, category=cls.cat, preparation_station=cls.salad)

    def post_json(self, url, data=None):
        return self.client.post(url, data=json.dumps(data or {}), content_type="application/json")


class LoginAndAccessTests(BaseCase):
    def test_1_user_login(self):
        self.assertTrue(self.client.login(username="w1", password="pass12345"))
        resp = self.client.post(reverse("login"), {"username": "w1", "password": "pass12345"})
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)
        from django.test import Client
        bad = Client().post(reverse("login"), {"username": "w1", "password": "wrong"})
        self.assertEqual(bad.status_code, 200)

    def test_inactive_user_cannot_login(self):
        self.waiter2.is_active = False
        self.waiter2.save()
        resp = self.client.post(reverse("login"), {"username": "w2", "password": "pass12345"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_2_waiter_access(self):
        self.client.login(username="w1", password="pass12345")
        self.assertEqual(self.client.get(reverse("sectors")).status_code, 200)
        self.assertEqual(self.client.get(reverse("sector_detail", args=[self.section.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 403)
        admin_resp = self.client.get("/admin/")
        self.assertEqual(admin_resp.status_code, 302)
        self.assertIn("/admin/login/", admin_resp["Location"])
        self.assertFalse(self.waiter.is_staff)

    def test_3_admin_access(self):
        self.client.login(username="admin1", password="pass12345")
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertRedirects(self.client.get(reverse("home")), reverse("dashboard:home"), fetch_redirect_response=False)

    def test_anonymous_redirected(self):
        resp = self.client.get(reverse("sectors"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])


class CatalogTests(BaseCase):
    def test_4_section_creation_and_admin_generate(self):
        self.client.login(username="admin1", password="pass12345")
        data = {
            "name": "Tapchan", "sort_order": 3, "active": "on", "generate_count": 5,
            "tables-TOTAL_FORMS": 0, "tables-INITIAL_FORMS": 0, "tables-MIN_NUM_FORMS": 0, "tables-MAX_NUM_FORMS": 1000,
        }
        resp = self.client.post("/admin/locations/section/add/", data)
        self.assertEqual(resp.status_code, 302)
        section = Section.objects.get(name="Tapchan")
        self.assertEqual(section.tables.count(), 5)
        self.assertTrue(section.active)

    def test_5_dining_table_creation(self):
        t = DiningTable.objects.create(section=self.section, name="T1", capacity=6)
        self.assertEqual(str(t), "Zal → T1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            DiningTable.objects.create(section=self.section, name="T1")

    def test_6_product_creation(self):
        p = Product.objects.create(name="Choy", price=8000, category=self.cat, preparation_station=self.bar)
        self.assertTrue(p.is_orderable)
        self.assertEqual(p.unit, "dona")
        p.available = False
        self.assertFalse(p.is_orderable)


class OrderFlowTests(BaseCase):
    def open(self, user=None):
        order, _ = services.open_order_for_table(self.table.pk, user or self.waiter)
        return order

    def test_7_order_creation(self):
        self.client.login(username="w1", password="pass12345")
        resp = self.client.post(reverse("open_table", args=[self.table.pk]))
        order = Order.objects.get()
        self.assertRedirects(resp, reverse("order_detail", args=[order.pk]), fetch_redirect_response=False)
        self.assertEqual(order.status, Order.Status.OPEN)
        self.assertEqual(order.waiter, self.waiter)
        self.assertEqual(self.client.get(reverse("order_detail", args=[order.pk])).status_code, 200)

    def test_8_adding_items(self):
        order = self.open()
        services.add_item(order.pk, self.waiter, self.lamb.pk, 2)
        services.add_item(order.pk, self.waiter, self.lamb.pk, 1)
        services.add_item(order.pk, self.waiter, self.spicy.pk, 1, "Achchiq bo‘lmasin")
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.items.get(product=self.lamb).quantity, 3)
        self.assertEqual(Order.objects.get(pk=order.pk).total, 3 * 25000 + 15000)
        item = order.items.get(product=self.lamb)
        services.set_item_quantity(order.pk, self.waiter, item.pk, 5)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 5)
        services.set_item_quantity(order.pk, self.waiter, item.pk, 0)
        self.assertFalse(order.items.filter(pk=item.pk).exists())

    def test_inactive_product_rejected(self):
        order = self.open()
        self.water.available = False
        self.water.save()
        with self.assertRaises(OrderError):
            services.add_item(order.pk, self.waiter, self.water.pk, 1)

    def test_9_price_snapshot(self):
        order = self.open()
        item = services.add_item(order.pk, self.waiter, self.lamb.pk, 2)
        self.lamb.price = 30000
        self.lamb.name = "Qo‘y shashlik (yangi)"
        self.lamb.save()
        item.refresh_from_db()
        self.assertEqual(item.unit_price, 25000)
        self.assertEqual(item.product_name, "Qo‘y shashlik")
        self.assertEqual(item.line_total, 50000)
        later = services.add_item(order.pk, self.waiter, self.lamb.pk, 1)
        self.assertEqual(later.unit_price, 30000)

    def test_10_order_sending_and_double_submit(self):
        order = self.open()
        services.add_item(order.pk, self.waiter, self.lamb.pk, 2)
        services.add_item(order.pk, self.waiter, self.water.pk, 2)
        with self.captureOnCommitCallbacks(execute=True):
            services.send_order(order.pk, self.waiter)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SENT)
        self.assertIsNotNone(order.sent_at)
        self.assertEqual(set(order.items.values_list("status", flat=True)), {OrderItem.Status.SENT})
        self.assertEqual(PrintJob.objects.filter(order=order).count(), 2)
        with self.assertRaises(OrderError):
            services.send_order(order.pk, self.waiter)
        self.assertEqual(PrintJob.objects.filter(order=order).count(), 2)
        # sent item cannot be edited
        item = order.items.first()
        with self.assertRaises(OrderError):
            services.set_item_quantity(order.pk, self.waiter, item.pk, 9)

    def test_send_via_api_twice(self):
        order = self.open()
        services.add_item(order.pk, self.waiter, self.lamb.pk, 1)
        self.client.login(username="w1", password="pass12345")
        first = self.post_json(reverse("order_send", args=[order.pk]))
        second = self.post_json(reverse("order_send", args=[order.pk]))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertFalse(second.json()["ok"])

    def test_resend_after_ready_becomes_partial(self):
        order = self.open()
        services.add_item(order.pk, self.waiter, self.lamb.pk, 1)
        services.send_order(order.pk, self.waiter)
        services.mark_items(order.pk, OrderItem.Status.READY)
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.READY)
        services.add_item(order.pk, self.waiter, self.water.pk, 1)
        services.send_order(order.pk, self.waiter)
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.PARTIAL)

    def test_11_station_filtering(self):
        order = self.open()
        services.add_item(order.pk, self.waiter, self.lamb.pk, 2)
        services.add_item(order.pk, self.waiter, self.water.pk, 2)
        services.add_item(order.pk, self.waiter, self.spicy.pk, 1, "Achchiq bo‘lmasin")
        items = list(order.items.select_related("station"))
        order = Order.objects.select_related("table__section", "waiter").get(pk=order.pk)
        jobs = print_items(order, items)
        by_station = {j.station.name: j.content for j in jobs}
        self.assertEqual(set(by_station), {"Gril", "Bar", "Salat"})
        self.assertIn("Qo‘y shashlik", by_station["Gril"])
        self.assertNotIn("Suv", by_station["Gril"])
        self.assertIn("Suv", by_station["Bar"])
        self.assertNotIn("Achchiq", by_station["Bar"])
        self.assertIn("Achchiq bo‘lmasin", by_station["Salat"])
        self.assertIn("Joy: 5", by_station["Gril"])

    def test_12_unauthorized_waiter_access(self):
        order = self.open(self.waiter)
        services.add_item(order.pk, self.waiter, self.lamb.pk, 1)
        self.client.login(username="w2", password="pass12345")
        self.assertEqual(self.client.get(reverse("order_detail", args=[order.pk])).status_code, 403)
        self.assertEqual(self.post_json(reverse("order_add", args=[order.pk]), {"product_id": self.water.pk}).status_code, 403)
        self.assertEqual(self.post_json(reverse("order_send", args=[order.pk])).status_code, 403)
        with self.assertRaises(PermissionDenied):
            services.add_item(order.pk, self.waiter2, self.water.pk, 1)
        resp = self.client.post(reverse("open_table", args=[self.table.pk]))
        self.assertRedirects(resp, reverse("sector_detail", args=[self.section.pk]), fetch_redirect_response=False)
        self.assertEqual(order.items.count(), 1)
        # administrator can
        self.client.login(username="admin1", password="pass12345")
        self.assertEqual(self.client.get(reverse("order_detail", args=[order.pk])).status_code, 200)

    def test_13_duplicate_active_order_protection(self):
        first, created1 = services.open_order_for_table(self.table.pk, self.waiter)
        second, created2 = services.open_order_for_table(self.table.pk, self.waiter2)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Order.objects.filter(table=self.table).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(table=self.table, waiter=self.waiter2)

    def test_inactive_table_rejects_new_order(self):
        self.table.active = False
        self.table.save()
        with self.assertRaises(OrderError):
            services.open_order_for_table(self.table.pk, self.waiter)

    def test_paid_order_frees_table(self):
        order = self.open()
        services.add_item(order.pk, self.waiter, self.lamb.pk, 2)
        services.send_order(order.pk, self.waiter)
        with self.assertRaises(PermissionDenied):
            services.pay_order(order.pk, self.waiter)
        services.pay_order(order.pk, self.admin, Payment.Method.CARD)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(Payment.objects.get().amount, 50000)
        new_order, created = services.open_order_for_table(self.table.pk, self.waiter2)
        self.assertTrue(created)
        self.assertNotEqual(new_order.pk, order.pk)

    def test_waiter_can_cancel_empty_order_only(self):
        order = self.open()
        services.cancel_order(order.pk, self.waiter)
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.CANCELLED)
        order2 = self.open()
        services.add_item(order2.pk, self.waiter, self.lamb.pk, 1)
        services.send_order(order2.pk, self.waiter)
        with self.assertRaises(OrderError):
            services.cancel_order(order2.pk, self.waiter)


class ApiAndDashboardTests(BaseCase):
    def setUp(self):
        self.order, _ = services.open_order_for_table(self.table.pk, self.waiter)
        self.client.login(username="w1", password="pass12345")

    def test_api_add_qty_note_remove(self):
        r = self.post_json(reverse("order_add", args=[self.order.pk]), {"product_id": self.lamb.pk, "quantity": 1})
        self.assertEqual(r.status_code, 200)
        item_id = r.json()["order"]["items"][0]["id"]
        r = self.post_json(reverse("order_qty", args=[self.order.pk, item_id]), {"delta": 1})
        self.assertEqual(r.json()["order"]["items"][0]["qty"], 2)
        r = self.post_json(reverse("order_qty", args=[self.order.pk, item_id]), {"delta": 1})
        self.assertEqual(r.json()["order"]["total"], 75000)
        r = self.post_json(reverse("order_note", args=[self.order.pk, item_id]), {"note": "Achchiq bo‘lmasin"})
        self.assertEqual(r.json()["order"]["items"][0]["note"], "Achchiq bo‘lmasin")
        r = self.post_json(reverse("order_qty", args=[self.order.pk, item_id]), {"quantity": 0})
        self.assertEqual(r.json()["order"]["items"], [])
        r = self.post_json(reverse("order_add", args=[self.order.pk]), {"product_id": self.water.pk})
        item_id = r.json()["order"]["items"][0]["id"]
        r = self.post_json(reverse("order_remove", args=[self.order.pk, item_id]))
        self.assertEqual(r.json()["order"]["items"], [])

    def test_api_rejects_get_and_bad_input(self):
        self.assertEqual(self.client.get(reverse("order_add", args=[self.order.pk])).status_code, 405)
        r = self.post_json(reverse("order_add", args=[self.order.pk]), {"product_id": 99999})
        self.assertEqual(r.status_code, 400)
        r = self.post_json(reverse("order_add", args=[self.order.pk]), {"product_id": self.lamb.pk, "quantity": 500})
        self.assertEqual(r.status_code, 400)

    def test_request_payment_and_reset_on_new_item(self):
        services.add_item(self.order.pk, self.waiter, self.lamb.pk, 1)
        self.assertEqual(self.post_json(reverse("order_request_payment", args=[self.order.pk])).status_code, 400)
        services.send_order(self.order.pk, self.waiter)
        self.assertEqual(self.post_json(reverse("order_request_payment", args=[self.order.pk])).status_code, 200)
        self.assertEqual(Order.objects.get(pk=self.order.pk).table_state, "pay")
        services.add_item(self.order.pk, self.waiter, self.water.pk, 1)
        self.assertFalse(Order.objects.get(pk=self.order.pk).payment_requested)

    def test_api_cancel_empty_order(self):
        r = self.post_json(reverse("order_cancel", args=[self.order.pk]))
        self.assertEqual(r.json()["redirect"], "/sectors/")
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.CANCELLED)

    def test_dashboard_actions_admin_only(self):
        services.add_item(self.order.pk, self.waiter, self.lamb.pk, 2)
        services.send_order(self.order.pk, self.waiter)
        url = reverse("dashboard:order_action", args=[self.order.pk, "pay"])
        self.assertEqual(self.client.post(url, {"method": "cash"}).status_code, 403)
        self.client.login(username="admin1", password="pass12345")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(reverse("dashboard:order_action", args=[self.order.pk, "ready"]))
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.READY)
        self.assertEqual(self.client.post(url, {"method": "cash"}).status_code, 302)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.PAID)
        for name in ("orders", "prints", "home"):
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:orders")).status_code, 200)

    def test_open_table_never_redirects_to_referer(self):
        self.table.active = False
        self.table.save()
        other = DiningTable.objects.create(section=self.section, name="9")
        other.active = False
        other.save()
        resp = self.client.post(reverse("open_table", args=[other.pk]), HTTP_REFERER="http://evil.example/")
        self.assertRedirects(resp, reverse("sectors"), fetch_redirect_response=False)

    def test_image_size_validator(self):
        from django.core.exceptions import ValidationError
        from menu.validators import validate_image_size

        class Big:
            size = 6 * 1024 * 1024

        with self.assertRaises(ValidationError):
            validate_image_size(Big())

    def test_pages_render_with_data(self):
        services.add_item(self.order.pk, self.waiter, self.lamb.pk, 1)
        for name, args in (("sectors", []), ("sector_detail", [self.section.pk]), ("my_orders", []), ("order_detail", [self.order.pk])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
