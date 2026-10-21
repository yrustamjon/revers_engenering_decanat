# Render’da saytni ishga tushirish

Bu yo‘l React va DRFni **bitta Web Service** va bitta origin orqali ishga tushiradi. PostgreSQL va Key Value (Redis) alohida xizmat bo‘ladi. `Dockerfile.render` ishlatiladi; odatiy `Dockerfile` Docker Compose uchun qoladi.

## 1. PostgreSQL va Key Value

Render dashboardda:

1. **New → Postgres**: nomi `uniflow-db`; Web Service bilan bir xil region, masalan Oregon. Database, username va parolni xavfsiz saqlang. Host sifatida **Internal Hostname** ishlatiladi.
2. **New → Key Value**: nomi `uniflow-cache`; xuddi shu region. **Internal Redis URL** ni oling.

Tarif, amal muddati va saqlash chegaralarini Render ko‘rsatgan shartlar bo‘yicha tanlang. Bu qo‘llanma pullik xizmatni avtomatik yaratmaydi. Parollar va ichki URLlarni chat yoki Gitga yubormang.

## 2. New Web Service oynasi

| Maydon | Qiymat |
| --- | --- |
| Repository | `yrustamjon/revers_engenering_decanat` |
| Name | Masalan `uniflow-web` |
| Language | `Docker` |
| Branch | `main` |
| Region | PostgreSQL/Key Value bilan bir xil |
| Root Directory | Bo‘sh qoldiring |
| Advanced → Dockerfile Path | `./Dockerfile.render` |
| Advanced → Docker Build Context Directory | `.` yoki standart repo ildizi |
| Advanced → Docker Command | Bo‘sh qoldiring; image entrypoint ishlaydi |
| Advanced → Health Check Path | `/healthz` |

Free Web Service interfeys va havolali hisobot jarayonini sinash uchun ishlatilishi mumkin. Free xizmat bo‘sh turganda uxlaydi. Uning doimiy diski yo‘q; shu sabab bu Dockerfile **fayl yuklashni standart holatda o‘chiradi**. Profil, portfel ma’lumotlari, dalil havolalari va hisobotlar PostgreSQLda saqlanadi. Tarif limitlari va DBning amal qilish muddatini Render dashboarddan tekshiring.

## 3. Environment Variables

| Key | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | **Generate** orqali uzun tasodifiy qiymat |
| `POSTGRES_HOST` | Postgres xizmatining Internal Hostname qiymati |
| `POSTGRES_PORT` | Postgres xizmati ko‘rsatgan port, odatda `5432` |
| `POSTGRES_DB` | Database nomi |
| `POSTGRES_USER` | Database foydalanuvchisi |
| `POSTGRES_PASSWORD` | Database paroli |
| `DJANGO_REDIS_URL` | Key Value xizmatining Internal Redis URL qiymati |
| `UNIFLOW_ADMIN_USERNAME` | Birinchi admin uchun tanlangan login |
| `UNIFLOW_ADMIN_PASSWORD` | Alohida kuchli parol, kamida 12–16 belgi tavsiya etiladi |
| `UNIFLOW_ADMIN_EMAIL` | Admin emaili, ixtiyoriy |

`DJANGO_DEBUG=0`, proxy HTTPS ishonchi va port image/startup orqali sozlangan. Renderning `PORT`, `RENDER=true` va `RENDER_EXTERNAL_HOSTNAME` o‘zgaruvchilarini qo‘lda almashtirmang. Render domeni avtomatik ALLOWED_HOSTS va CSRF origin sifatida olinadi.

Custom domain qo‘shilganda `DJANGO_ALLOWED_HOSTS` ga Render hosti va yangi hostni vergul bilan, `DJANGO_CSRF_TRUSTED_ORIGINS` ga ikkala to‘liq `https://...` originni kiriting. Wildcard ishlatmang.

## 4. Deploy va hisobga kirish

**Deploy Web Service** bosing. Build Reactni yig‘adi, Python paketlarini o‘rnatadi. Startup migratsiya, Django static va birinchi administratorni yaratadi. Gunicorn `0.0.0.0:$PORT` da ishlaydi.

Deploy tugagach Render bergan HTTPS manzilni oching. Saytdagi login formasiga `UNIFLOW_ADMIN_USERNAME` va `UNIFLOW_ADMIN_PASSWORD` qiymatlarini kiriting. Productionda avtomatik demo login yo‘q. Boshqaruvdan bo‘lim, haqiqiy shablon va xodim hisoblarini yarating.

Admin yaratilib kirish tekshirilgach, **ikkala** `UNIFLOW_ADMIN_USERNAME` va `UNIFLOW_ADMIN_PASSWORD` bootstrap o‘zgaruvchisini olib tashlash mumkin. Keyingi deploy mavjud admin parolini almashtirmaydi. Hisobni o‘chirish/faolsizlantirishni bootstrap orqali qaytarib bo‘lmaydi.

## 5. Tekshiruv va doimiy fayllar

- `/healthz` 200: ilova DB va cachega ulana oladi. Nosozlikda credential tafsilotisiz 503 qaytadi.
- Bosh sahifa va `/assets/` frontendni, `/api/` DRFni bir hostdan beradi.
- Havolali faoliyat → report → boshqa tekshiruvchi qarori → arxiv jarayonini tekshiring.
- Free muhitda fayl yuklash saqlash xizmati sozlanmaganini bildiradi; fayl jim qabul qilinib keyingi deployda yo‘qolmaydi.
- Faylli hujjatlar uchun doimiy diskli Web Service yoki himoyalangan obyekt saqlash kerak. Disk yo‘li `DJANGO_MEDIA_ROOT` bilan mos, ilova foydalanuvchisiga yoziladigan bo‘lsin. Shundan keyin `DJANGO_UPLOADS_ENABLED=1`; fayl yuklash, download vakolati va **redeploydan keyin fayl qolishi** tekshirilsin. Zaxira/tiklash ham alohida bajariladi.

Renderdagi haqiqiy deploy, disk va tashqi HTTPS sinovi bajarilmaguncha lokal Docker sinovi ularning muvaffaqiyati deb hisoblanmaydi. [Qolgan ishlar](REMAINING_WORK.md) dagi audit, yuborilgan nusxalar, IP zanjiri va saqlash siyosati pilot talablari bo‘lib qoladi. Telegram xizmatining restarti ushbu sayt deployidan alohida.

2026-10-22 lokal tekshiruv: `Dockerfile.render` yig‘ildi; PostgreSQL/Redis bilan **47 backend testi o‘tdi**. Konteyner Renderga o‘xshash hostname va nostandart `PORT` bilan `healthy` bo‘ldi. React/JS, API, avtomatik host/CSRF origin, birinchi admin orqali kirish, CSRF va saqlashsiz faylni rad etish jonli lokal Gunicorn orqali tekshirildi. Tashqi Render hisobida xizmat ushbu ish davomida yaratilmagan.
