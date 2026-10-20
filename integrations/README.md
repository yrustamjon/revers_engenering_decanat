# Telegram loyiha boti

Bu ixtiyoriy Python worker loyiha holatini yuboradi va faqat oldindan belgilangan **bitta shaxsiy chat** xabarlarini qabul qiladi. Xabarlar AI so‘rovi, terminal buyrug‘i yoki dastur sifatida bajarilmaydi. Qabul tasdig‘i xabarni inson yoki faol yordamchi o‘qiganini anglatmaydi.

## Sozlash

Cloud muhitida mavjud `tg_key` secret bog‘lanishidan foydalaniladi. Muqobil nom: `UNIFLOW_TELEGRAM_TOKEN`. `UNIFLOW_TELEGRAM_CHAT_ID` ga o‘zingizning musbat shaxsiy Telegram ID raqamingizni qo‘ying. Tarmoq siyosatida `api.telegram.org` HTTPS manziliga ruxsat kerak.

Tokenni Git, kod, buyruq argumentlari yoki logga yozmang. Agar token chatda yoki boshqa ochiq joyda ulashilgan bo‘lsa, BotFather orqali almashtiring. Kerak bo‘lsa `--token-file` bilan joriy foydalanuvchiga tegishli, `0600` ruxsatli oddiy token faylini tanlang. Standart mahalliy token fayli `.local/telegram/token`; `.local/` Git’dan chiqarib tashlanishi kerak. Ramziy havolalar va ochiq ruxsatli token fayllari rad etiladi.

Avval Telegram ilovasida botni ochib `/start` yuboring. Bot foydalanuvchi suhbatni boshlamaguncha unga o‘zi birinchi bo‘lib yoza olmaydi.

Repozitoriy ildizidan:

```sh
python integrations/telegram_bot.py --check
python integrations/telegram_bot.py --send 'UniFlow ish maydoni tayyorlanmoqda.'
python integrations/telegram_bot.py --poll --status-file .local/telegram/status.json
```

Token fayli orqali ishlaganda har bir buyruqqa `--token-file <xavfsiz-fayl>` qo‘shish mumkin. Token qiymatini buyruqqa yozish shart emas. Maxfiy bo‘lmagan chat ID ni `--chat-id <shaxsiy-ID>` orqali ham berish mumkin; bu holda `UNIFLOW_TELEGRAM_CHAT_ID` talab qilinmaydi.

`status.json` namunasi (maxfiy ma’lumot kiritmang):

```json
{"summary":"Hisobot aylanishi sinovdan o‘tdi.","stage":"Administrator qismini tekshirish","updated_at":"2026-10-20"}
```

## Xabarlar va qayta ishga tushirish

- `/start`, `/help`: bot vazifasi va buyruqlar.
- `/status`: status faylining `summary`, `stage`, `updated_at` qiymatlari.
- Boshqa matn: `.local/telegram/inbox.jsonl` ga yoziladi va avtomatik qabul tasdig‘i beriladi.
- Boshqa chatlar, guruhlar va boshqa yuboruvchilar e’tiborsiz qoldiriladi.
- Inbox fayli `0600`, papka `0700`. Token va uning URL’i diagnostikaga chiqarilmaydi.
- Offset har qayta ishlangan yangilanishdan keyin atomar saqlanadi. Javob jo‘natish uzilsa, xabar qayta qabul qilinganda inboxda takrorlanmaydi.
- Bir muhitda bitta polling jarayonini ishlating. Lock ikkinchi jarayonni to‘xtatadi. Telegram `409` javobi boshqa polling yoki faol webhook borligini bildiradi; worker webhookni o‘zi o‘chirmaydi.
- `429` javobida Telegram tavsiya qilgan vaqt kutiladi. TLS/CA tekshiruvi va meros olingan proksi sozlamalari saqlanadi.

Polling tirik jarayonga bog‘liq. Cloud muhiti qayta ishga tushganda `--poll` buyrug‘ini startup ko‘rsatmalari yoki o‘z process manager’ingiz orqali qayta boshlang. Fayllar saqlangani jarayon ham saqlanadi degani emas.

## Sinovlar

```sh
python -m unittest discover -s integrations/tests -v
```

Sinovlar haqiqiy Telegram tarmog‘i yoki tokenidan foydalanmaydi. Jonli ulanish faqat `--check` muvaffaqiyatli bo‘lgandan keyin tasdiqlangan hisoblanadi.
