# UniFlow

Universitet xodimlari uchun **React + TypeScript** va **Django REST Framework** asosidagi elektron portfel, ish rejasi va hisobot platformasi. Interfeys o‘zbek tilida, kompyuter va telefonga mos.

Xodim natijalarini bir marta kiritadi, ulardan hisobot tayyorlaydi. Mas’ul dalillarni tekshiradi, izoh bilan qaytaradi yoki tasdiqlaydi. Yakuniy hisobot arxivda saqlanadi va chop etilishi yoki brauzerdan PDF shaklida olinishi mumkin.

TATU nomi foydalanish konteksti sifatida olingan. Namuna ma’lumotlari universitetning rasmiy bazasi yoki ichki reglamenti emas.

## Ishlaydigan imkoniyatlar

- **Ish stoli:** saqlangan ma’lumotlardan hisoblanadigan ko‘rsatkichlar, faoliyat grafigi, reja bajarilishi va so‘nggi hisobotlar.
- **Shaxsiy portfel:** maqola, konferensiya, sertifikat, uslubiy ish va loyiha; fayl yoki manba havolasi; qidiruv va filtrlar.
- **Hisobotlar:** qoralama → yuborish → tekshirish → izoh bilan qaytarish → tuzatish → qayta yuborish → tasdiqlash → arxiv.
- **Versiyali shakllar:** administrator maxsus matn, son, sana yoki havola maydonlari qo‘shadi. Majburiy maydonlar serverda ham tekshiriladi. Hisobot shablonning o‘sha paytdagi nusxasini saqlaydi.
- **Ish rejasi:** maqsadlar, bajarilgan miqdor, muddatlar va bajarilish foizi.
- **Profil:** shaxsiy ma’lumotlarni tahrirlash; tashkiliy ma’lumotlarni faqat vakolatli administrator boshqaradi.
- **Boshqaruv:** haqiqiy xodim hisoblari, rollar, bo‘limlar, shablonlar va hisobni faolsizlantirish.
- **Hisob himoyasi:** sessiya va CSRF, parol almashtirish, kirish urinishlarini cheklash, kafedra bo‘yicha ko‘rish vakolati, muallifning o‘z hisobotini tasdiqlashini taqiqlash.
- **Hujjat yaxlitligi:** tekshiruvdagi yoki tasdiqlangan hisobot va uning dalillarini tahrirlash bloklanadi. Fayllar autentifikatsiyalangan endpoint orqali yuklab olinadi.
- **Bildirishnomalar, umumiy qidiruv, chop etish va yordam qo‘llanmasi.**
- **Ixtiyoriy Telegram worker:** faqat belgilangan shaxsiy chat uchun loyiha holati, xabar qabul qilish va yuborish. Kiruvchi xabarlar buyruq sifatida bajarilmaydi.
- **Telegram Codex assistant:** alohida davomli suhbat, oddiy savollar uchun o‘qish rejimi, `/task` uchun loyiha ustida ishlash, navbat va bekor qilish. Haqiqiy model kirishi va ishlayotgan xizmat talab qilinadi.

## Mahalliy ishga tushirish

Talablar: **Python 3.12+**, **Node.js 22+**, npm. Python virtual muhiti, SQLite va lokal fayl saqlash ishlab chiqish uchun ishlatiladi.

Windows PowerShell uchun [alohida o‘rnatish va ishga tushirish qo‘llanmasi](docs/WINDOWS.md) bor.

Repozitoriy ildizidan:

```bash
bash scripts/setup.sh --demo
bash scripts/dev.sh
```

Frontend **5173**, backend **8000** portida ishlaydi. Vite `/api` so‘rovlarini backendga yo‘naltiradi. `Ctrl+C` ikkala xizmatni to‘xtatadi. `setup.sh --demo` namuna yozuvlarini yaratadi; qayta ishga tushirilganda mavjud tahrirlarni saqlaydi.

Namuna muhitda xodim kabineti avtomatik ochiladi. Yuqori o‘ngdagi profil menyusidan **Tekshiruvchi** va **Administrator** kabinetlariga o‘tish mumkin. Namunaviy kirish faqat `DJANGO_DEBUG=1` rejimida mavjud.

Haqiqiy hisob bilan ishlash uchun administrator kabinetida xodim yarating. Namunasiz muhit uchun `bash scripts/setup.sh` bajaring va birinchi administratorni yarating:

```bash
.venv/bin/python backend/manage.py createsuperuser
```

### Xizmatlarni alohida boshlash

```bash
# Repozitoriy ildizida, birinchi terminal:
.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload

# Ikkinchi terminal:
npm run dev --prefix frontend
```

## Tekshirish

```bash
.venv/bin/python backend/manage.py test core --verbosity 2
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build --prefix frontend
python -m unittest discover -s integrations/tests -v

# Ikkala xizmat ishlayotganida:
npm run test:e2e --prefix frontend
```

Brauzer sinovlari Chromium ishlatadi. Cloud muhitda `/usr/bin/chromium` mavjud. Boshqa tizimda `CHROMIUM_PATH` bilan brauzer yo‘lini belgilang yoki Playwright Chromium o‘rnating. Sinovlar fayl yuklash, to‘liq hisobot jarayoni, vakolatlar, profil, reja, boshqaruv va mobil sahifalarni tekshiradi. Brauzer sinovlarini alohida sinov bazasida yoki faqat namuna muhitida bajaring.

## Tuzilma

```text
frontend/       React, TypeScript, Vite, Lucide, Playwright
backend/        Django, DRF, modellar, migratsiyalar va jarayon sinovlari
integrations/   Mustaqil Telegram status/xabar worker va uning sinovlari
scripts/        Takrorlanadigan o‘rnatish va xizmatlarni boshlash
docs/           Mahsulot rejasi, API va ishga chiqarish hujjatlari
```

- [To‘liq mahsulot rejasi](docs/PRODUCT_PLAN.md)
- [Tekshiruv natijasi va qolgan ishlarning ustuvor rejasi](docs/REMAINING_WORK.md)
- [API shartnomasi](docs/api-contract.md)
- [Backend va autentifikatsiya](backend/README.md)
- [Telegram integratsiyasi](integrations/README.md)
- [Telegram orqali Codex bilan suhbat va loyiha topshiriqlari](docs/TELEGRAM_ASSISTANT.md)
- [PostgreSQL, Docker va HTTPS orqali ishga chiqarish](docs/DEPLOYMENT.md)

## Amaliy joriy qilish chegaralari

Hozir hisobot bo‘yicha bitta vakolatli tekshiruvchi qarori mavjud. Ko‘p bosqichli kelishish, nomzodni ishga qabul qilish, rasmiy kadrlar hujjatlari, umumuniversitet jamlama hisobotlari, HEMIS, E-IMZO va buxgalteriya integratsiyasi mahsulot rejasida alohida ko‘rsatilgan. Ular universitetning haqiqiy shakllari, vakolatlari va API ruxsatlariga tayangan holda bajariladi. Ichki tasdiq ERI o‘rnini bosmaydi va maqola kiritish avtomatik ish haqi tayinlamaydi.

Ishchi muhitga chiqarishda DEBUG o‘chirilishi, haqiqiy domen/HTTPS, alohida maxfiy kalitlar, doimiy himoyalangan saqlash va zaxiradan tiklash sinovi talab qilinadi. Tokenlar, `.env`, bazalar, yuklangan hujjatlar va `.local/` Git’ga kiritilmaydi.
