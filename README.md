# Qassob Shashlik CRM

Restoran ofitsiantlari uchun buyurtma olish tizimi (CRM/POS prototipi). Ofitsiant restoran Wi-Fi tarmog‘iga ulangan **telefon** orqali kiradi, sektor va joyni tanlaydi, rasmli menyudan buyurtma yig‘adi va yuboradi. Buyurtma avtomatik ravishda tayyorlash bo‘limlariga (Gril, Bar, Salat, Oshxona...) ajratiladi va har bir bo‘lim printeriga faqat o‘z mahsulotlari chop etiladi.

**Texnologiyalar:** Python 3.11+, Django 5.1/5.2, PostgreSQL, Django Templates + Fetch (AJAX), Pillow, ESC/POS (TCP 9100).

## Imkoniyatlar

- Ikki rol: **Administrator** (to‘liq boshqaruv, `/admin/` va `/dashboard/`) va **Ofitsiant** (faqat ofitsiant paneli; Django Admin'ga kira olmaydi).
- Dinamik sektorlar, joylar, kategoriyalar, mahsulotlar, bo‘limlar — hammasi admin orqali (kodda hardcode yo‘q).
- Mobile-first panel: sektorlar → joylar (BO‘SH / BAND / BUYURTMA YUBORILGAN / TAYYOR / TO‘LOV KUTILMOQDA) → rasmli menyu → savat (`− 1 +`, izoh, o‘chirish) → **BUYURTMANI YUBORISH**.
- Narx snapshoti: `OrderItem.product_name` va `unit_price` buyurtma vaqtida saqlanadi.
- Concurrency: `transaction.atomic` + `select_for_update`, bitta joyga bitta faol buyurtma (DB darajasidagi partial unique constraint bilan ham himoyalangan), ikki marta yuborishdan himoya.
- Printer: ESC/POS tayyor arxitektura, printer topilmasa tizim buzilmaydi, **print preview** (Dashboard → Cheklar).
- Dashboard: bugungi buyurtmalar, tushum, faol buyurtmalar, band joylar, ofitsiantlar, eng ko‘p sotilgan mahsulotlar; buyurtmalar ro‘yxatida "Hammasi tayyor", "To‘lov qabul qilish", "Bekor qilish".

## Loyiha tuzilmasi

```
config/      sozlamalar, asosiy URL
accounts/    User (rol), login/logout, dekoratorlar (waiter_required, admin_required)
locations/   Section, DiningTable, ofitsiant bosh sahifasi va joylar ekrani
menu/        Category, Product
printing/    Station, Printer, PrintJob, ESC/POS (escpos.py), yuborish (services.py)
orders/      Order, OrderItem, biznes logika (services.py), API view'lar, seed_demo, testlar
payments/    Payment
dashboard/   administrator dashboardi
templates/, static/, media/
```

## O‘rnatish

### 1. Virtual environment

Windows (PowerShell):
```powershell
cd qassob_shashlik
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Linux/macOS:
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. PostgreSQL

```sql
CREATE DATABASE qassob_shashlik;
```
Foydalanuvchi va parolni `.env` ga yozing.

### 3. `.env`

```bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux/macOS
```
`.env` ichida `SECRET_KEY`, `DB_*` qiymatlarini to‘ldiring. (Faqat tez sinov uchun `DB_ENGINE=sqlite` ishlatish mumkin.)

### 4. Migratsiya, admin, demo ma’lumot

```bash
python manage.py migrate
python manage.py createsuperuser      # administrator (roli avtomatik "admin" bo'ladi)
python manage.py seed_demo            # ixtiyoriy: demo sektorlar, joylar, menyu, foydalanuvchilar
python manage.py runserver 0.0.0.0:8000
```

`seed_demo` yaratadi: `admin / admin12345`, `ofitsiant / ofitsiant12345`; sektorlar Zal (17), Ko‘cha (8), Tapchan (10: T1–T10), Kabina (5: K1–K5); bo‘limlar Oshxona, Gril, Salat, Bar; demo menyu. **Demo parollarni darhol almashtiring.** Buyruqni qayta ishga tushirish xavfsiz (mavjudlarini takrorlamaydi).

### 5. Testlar

```bash
python manage.py test
```

## Administrator qo‘llanmasi

`http://SERVER_IP:8000/admin/` — login qilgandan so‘ng:

1. **Tayyorlash bo‘limlari** — bo‘lim yarating, ichida printer (IP/port) qo‘shing.
2. **Sektorlar** — sektor yarating. "Avtomatik joy yaratish" maydoniga `17` yozsangiz, 1…17 joylar yaratiladi; yoki pastdagi jadvalda qo‘lda qo‘shing (masalan `T1`, `K1`).
3. **Kategoriyalar** va **Mahsulotlar** — rasm yuklash, narx, birlik, bo‘lim.
4. **Foydalanuvchilar** — ofitsiant yarating (rol: Ofitsiant). O‘chirish o‘rniga "Faol" belgisini olib tashlang (deaktivatsiya).

Dashboard: `http://SERVER_IP:8000/dashboard/`.

## Lokal Wi-Fi orqali ishlatish (Windows)

1. Kompyuter va telefonlar **bitta Wi-Fi** tarmog‘iga ulangan bo‘lsin.
2. Serverning IP manzilini toping: `cmd` → `ipconfig` → "IPv4 Address" (masalan `192.168.1.100`). Router sozlamasida shu kompyuterga **doimiy (static/DHCP reservation) IP** bering.
3. `.env`: `DEBUG=True`, `ALLOWED_HOSTS=*` (yoki `192.168.1.100,localhost`). Agar `DEBUG=False` bo‘lsa va HTTP orqali kirsangiz, `CSRF_TRUSTED_ORIGINS=http://192.168.1.100:8000` qo‘shing.
4. Serverni ishga tushiring: `python manage.py runserver 0.0.0.0:8000`
5. Windows Firewall'da 8000-portga ruxsat bering (PowerShell, administrator sifatida):
   ```powershell
   New-NetFirewallRule -DisplayName "Qassob CRM 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
   ```
6. Telefonda brauzerni oching: `http://192.168.1.100:8000` — login/parol bilan kiring.

Tizim internetsiz ham ishlaydi: barcha fayllar (CSS/JS) lokal, tashqi CDN ishlatilmaydi.

## Termal printer arxitekturasi

- Har bir mahsulot **tayyorlash bo‘limiga** (`Station`) biriktiriladi; har bir bo‘limga bir yoki bir nechta `Printer` (IP:port) bog‘lanadi.
- Buyurtma yuborilganda (`orders.services.send_order`) tranzaksiya commit bo‘lgach `printing.services.print_items` ishlaydi: yangi mahsulotlar bo‘lim bo‘yicha guruhlanadi va har bir bo‘lim faqat o‘z mahsulotlarining chekini oladi.
- Chek matni `printing/escpos.py` da yasaladi (32 ustun, o‘zgartirish: `PRINT_WIDTH`), ESC/POS baytlariga o‘giriladi (init, qalin/katta sarlavha, kesish) va TCP (odatda 9100) orqali yuboriladi.
- `PRINT_MODE=preview` (standart) — printerga yuborilmaydi, chek **Dashboard → Cheklar** da ko‘rinadi (rivojlanish rejimi).
- `PRINT_MODE=network` — haqiqiy printerga yuboriladi. Printer o‘chiq bo‘lsa yoki bo‘lim uchun faol printer yo‘q bo‘lsa, buyurtma baribir saqlanadi; `PrintJob` holati `FAILED`/`PREVIEW` bo‘ladi va admin paneldan "Qayta chop etish" mumkin.
- Chekda lotin harflari ASCII ga o‘giriladi (`o‘` → `o'`), chunki ko‘pchilik termal printerlar Unicode'ni qo‘llamaydi.

## Production ogohlantirishi

Bu **prototip**. Haqiqiy ishlatishdan oldin:

- `DEBUG=False`, uzun tasodifiy `SECRET_KEY`, aniq `ALLOWED_HOSTS`.
- Demo parollarni almashtiring, kuchli parollar ishlating.
- `runserver` o‘rniga gunicorn/waitress + Nginx (yoki Caddy), statik fayllar uchun `collectstatic`, media fayllarni serverdan xizmat qildirish. HTTPS ishlatilsa `SECURE_COOKIES=True`.
- PostgreSQL zaxira nusxasi (backup) rejasi.
- Printerlarni haqiqiy qurilmada sinab ko‘ring (kodlash/kesish buyrug‘i modelga qarab farq qilishi mumkin).
