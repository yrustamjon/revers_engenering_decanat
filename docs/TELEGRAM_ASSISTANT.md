# Telegram orqali UniFlow bilan ishlash

Bu integratsiya Telegramdagi bitta ruxsat berilgan shaxsiy chatni **alohida, davomli Codex CLI sessiyasiga** ulaydi. Bu saytdagi xodimlar uchun ommaviy chatbot emas. Brauzerdagi avvalgi hosted Codex suhbati avtomatik ko‘chirilmaydi; loyiha konteksti `integrations/PROJECT_CONTEXT.md`, manba kodi va Git tarixi orqali beriladi.

## Foydalanish

- Oddiy matn — loyiha haqida savol yoki suhbat. Codex `read-only` rejimida ishlaydi.
- `/task <topshiriq>` — loyiha ichida kod o‘zgartirish va sinash uchun `workspace-write` topshirig‘i.
- `/status` — joriy ish va navbat holati.
- `/cancel` — hozir bajarilayotgan topshiriqni to‘xtatish.
- `/new` — ish va navbat bo‘sh bo‘lganda yangi suhbat boshlash.
- `/help` — qo‘llanma.

Misollar:

```text
Hisobotni tasdiqlash hozir qanday ishlaydi?
/task Hisobotlar jadvaliga hujjat turi bo‘yicha filtr qo‘sh va test qil.
/task Profil sahifasidagi telefon tekshiruvini tuzat, test qil va main’ga push qil.
```

Git push faqat aynan joriy topshiriqda so‘ralganda bajariladi. Kiruvchi matn shell buyrug‘i sifatida avtomatik bajarilmaydi. Sandbox va tasdiqlash cheklovlari o‘chirilmaydi.

## Kerakli muhit

Linux, Python 3.12+, Git va rasmiy Codex CLI kerak. Codex CLI o‘rnatilgan foydalanuvchi hisobida `codex login` orqali kirilgan bo‘lishi kerak. ChatGPT orqali kirish qo‘llab-quvvatlangan hisoblarda alohida API kaliti shart emas. Faqat `codex login status`ning muvaffaqiyatli chiqishi model so‘rovining ishlashini isbotlamaydi; quyidagi jonli tekshiruvni bajaring.

Telegram credentiali mavjud `tg_key` yoki `UNIFLOW_TELEGRAM_TOKEN` bindingidan olinadi. Muqobil: `.local/telegram/token` fayli joriy foydalanuvchiga tegishli va `0600` ruxsatli bo‘lishi kerak. Shaxsiy chat ID `UNIFLOW_TELEGRAM_CHAT_ID` yoki `.local/telegram/chat_id` orqali beriladi. Credentialni argumentga, repozitoriyga yoki logga yozmang. `.local/` Git’dan chiqarilgan.

Codex o‘z odatiy xizmat papkasida `installation_id` va sessiya fayllarini yaratishi kerak. Boshqa joydagi log va SQLite holati bridge’ning shaxsiy papkasiga yo‘naltiriladi. Read-only authenticated Codex home’ni credentiallarni boshqa joyga nusxalash yoki sandboxni o‘chirish orqali aylanib o‘tmang; muhitning qo‘llab-quvvatlangan yozish ruxsatini sozlang.

Tarmoqdan `api.telegram.org` va ChatGPT orqali kiruvchi Codex uchun `chatgpt.com` kerak. Mavjud proksi va CA ishonchi saqlanadi. Qo‘shimcha autentifikatsiya manzili kerak bo‘lsa, aniq so‘rov xatosi asosida qo‘shiladi.

## Ishga tushirish

Repozitoriy ildizida:

```bash
# Telegram token/kirishini tekshirish:
bash scripts/telegram.sh --check

# Haqiqiy minimal Codex so‘rovi va javobini tekshirish:
bash scripts/telegram-assistant.sh --check-codex

# Yuqoridagi tekshiruvdan keyin:
bash scripts/telegram-assistant.sh --poll
```

Eski `telegram.sh --poll` holat boti va yangi assistant bitta polling lockdan foydalanadi. Yangi xizmatni boshlashdan oldin faqat o‘zingiz boshlagan eski jarayonni to‘xtating; bitta token bilan ikkita polling jarayoni ishlamasin.

## Holat va qayta boshlash

Navbat, suhbat ID, offset va javob yetkazish holati `.local/telegram/` ichida saqlanadi. Ular credentiallar bilan birga shaxsiy runtime fayllardir. Bot qayta boshlanganida bajarilishi tugamagan kod topshirig‘i avtomatik qayta bajarilmaydi: qisman o‘zgartirishlar takrorlanmasligi uchun uzilgan deb belgilanadi. Tayyor javobni Telegramga yetkazish muvaffaqiyatsiz bo‘lsa, model topshirig‘ini boshidan bajarish o‘rniga saqlangan javob qayta yuboriladi.

`/cancel` jarayonni to‘xtatadi; allaqachon yozilgan fayllarni yoki yuborilgan Git commitni avtomatik qaytarmaydi. So‘ng Git holatini tekshirish kerak.

Mavjud terminal, cloud muhit yoki kompyuter to‘xtasa, bot ham to‘xtaydi. Doimiy Linux serverda `deploy/telegram-assistant.service` systemd namunasi bor. Yo‘llar, service foydalanuvchisi va o‘sha foydalanuvchining Codex kirishini moslang; unit secret saqlamaydi. Service foydalanuvchisi repozitoriy va o‘z runtime holatiga yozish huquqiga ega bo‘lsin.

## Sinovlar va tayyorlik

```bash
python -m unittest discover -s integrations/tests -v
```

Offline testlar soxta CLI/Telegram transporti bilan sessiya davomiyligi, navbat, ruxsatlar, bekor qilish va qayta yetkazishni tekshiradi. Ular haqiqiy model javobi o‘rnini bosmaydi. Model so‘rovi, haqiqiy Telegram xabari va davomli sessiya sinovi o‘tmaguncha assistantni jonli ishlayapti deb hisoblamang.

Cloud konfiguratsiyasi draftiga domen qo‘shilishi uni joriy muhitga avtomatik qo‘llamaydi. Proxy `403` qaytarsa, environment settings’da ruxsatni ko‘rib saqlash va muhitni publish qilish kerak; proxy yoki TLS tekshiruvini chetlab o‘tmang.
