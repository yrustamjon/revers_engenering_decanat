# UniFlow ishlaydigan MVP

2026-10-22 relizi xodim → dalil → hisobot → tekshiruvchi → tuzatish → tasdiq → arxiv jarayonini haqiqiy hisoblarda bajaradi. Brauzer avtomatik demo hisobga kirmaydi. `auth/demo/` olib tashlangan; foydalanuvchi login/parol bilan kiradi, chiqadi va sessiyasi serverda bekor qilinadi.

## Qabul qilish mezonlari

| Jarayon | Natija |
| --- | --- |
| Boshlash | Toza DBga migrate; birinchi administrator `createsuperuser` yoki Render bootstrap orqali yaratiladi. Demo seed kerak emas. |
| Kirish/chiqish | Noto‘g‘ri parol rad etiladi; to‘g‘ri login sessiyasi reload’da qoladi; logout va muddati tugagan sessiya himoyalangan ma’lumotni ochmaydi. |
| Hisob boshqarish | Administrator bo‘lim, xodim va tekshiruvchi yaratadi; deactivation mavjud sessiyani ham to‘xtatadi; oxirgi administrator himoyalangan. |
| Vakolat | Xodim o‘z yozuvlarini ko‘radi; boshqa xodimning faylini ocholmaydi; tekshiruvchi o‘zini tasdiqlay olmaydi va admin ma’lumotiga kira olmaydi. |
| Hisobot | Faol shablon, kerakli maydonlar va owned dalil tekshiriladi; yuborish → izoh bilan qaytarish → tahrir → qayta yuborish → tasdiq ishlaydi. |
| Nusxalar | Har yuborish report/javob/faoliyat va fayl reference’larining alohida nusxasini yaratadi. Oldingi nusxa va tarixiy fayl tegishli mas’ulga ochiladi; begona reviewerga ochilmaydi. |
| Saqlash | Bir marta yuborilgan hisobotni oddiy DELETE yo‘qotmaydi. Tasdiqlangan hisobot va dalil tahrirdan himoyalangan. |
| Tashkiliy yo‘l | Birinchi yuborishda tekshiruv bo‘limi saqlanadi. Xodim ko‘chirilsa eski report vakolati ko‘chmaydi; bo‘lim rename’i o‘sha yo‘lni saqlaydi. |
| Audit | Hisob/vakolat, bo‘lim va shablon o‘zgarishlari oldingi/keyingi qiymatlar bilan faqat administratorga ko‘rinadi. Parol/hash auditga yozilmaydi. API va Django admin’dan audit/nusxa tahriri yo‘q. |
| DB yaxlitligi | Bo‘sh bo‘lmagan xodim ID va bo‘lim nomlari uchun case-insensitive DB uniqueness bor; parallel conflict umumiy validation javobiga aylantiriladi. |
| Interfeys | Mobil fokus, kontrast, shaxsiy statistikalar, qidiruv, haqiqiy bo‘sh holatlar va noma’lum hash route’lariga qaytish ishlaydi. |
| Ishchi image | React va DRF bir origin; non-root, runtime’da o‘rnatish vositalari yo‘q. PostgreSQL/Redis readiness va avtomatik initial admin tekshiriladi. |
| DevSecOps | [CI, scanner, release va backup/tiklash](DEVSECOPS.md) ish jarayoniga qo‘shilgan. Server-side branch protection va haqiqiy host sozlamalari alohida. |

## Eski ma’lumotni yangilash

Migratsiyalar mavjud yozuvlarni o‘chirmaydi. Eski yuborilgan hisobot yo‘li hozirgi ma’lum kafedraga bir marta bog‘lanadi; avvalgi aniq mansublikni tizim o‘zi ixtiro qilmaydi. Yangi submission nusxalari relizdan keyingi yuborishlarda olinadi; oldingi tahrirlarning mavjud bo‘lmagan mazmuni qayta yaratilmaydi. Eski shablonsiz draftni faol shablon bilan yangidan tayyorlash kerak.

Yangi unique constraint eski bazadagi takroriy ID/nomni qabul qilmaydi. Production migratsiyasidan oldin takrorlarni tekshirib mas’ul bilan tuzating; yozuvlarni jim o‘chirib yuborish yo‘q. Zaxira va tiklash juftligi saqlansin.

## Lokal foydalanish

```bash
bash scripts/setup.sh
.venv/bin/python backend/manage.py createsuperuser
bash scripts/dev.sh
```

`http://127.0.0.1:5173` da administrator paroli bilan kiring, bo‘lim va ikki alohida xodim/tekshiruvchi yarating. Bir xodim bajarilgan ishini dalil bilan saqlaydi; tekshiruvchi boshqa hisob bilan kirib qaror beradi. Bir-birining rolini parolsiz almashtirish yo‘q.

## Pilot chegarasi

MVP bitta tekshiruv bosqichini bajaradi. Universitetning haqiqiy shakli va vakolatini konfiguratsiya qiling. Ko‘p bosqichli kelishish, HR/ishga qabul, fakultet jamlamasi, rasmiy ERI/HEMIS/buxgalteriya keyingi mahsulot bosqichlari; ular ishlayapti deb ko‘rsatilmaydi.

Haqiqiy deployment uchun domen/HTTPS, proxy CIDR, doimiy private media, monitoring va off-host backup kerak. Render Free’da doimiy disk bo‘lmagani sabab fayl yuklash standart holatda o‘chiq; havola dalili ishlaydi. Lokal Compose recovery mashqi haqiqiy Render hostining backup/tiklanishini tasdiqlamaydi. Telegram AI ulanishi bu MVP relizidan alohida.

## Lokal tekshiruv dalillari — 2026-10-22

- Haqiqiy login/logout va hisobot jarayoni: Playwright’da 17 ta test o‘tdi.
- PostgreSQL va Redis bilan yakuniy konteynerda 56 ta backend testi o‘tdi; SQLite’da 55 ta o‘tdi, Redisga xos bittasi o‘tkazib yuborildi.
- Non-root image’da React asset, health, CSRF, login/logout va yopiq media tekshirildi.
- Konteyner skanida HIGH/CRITICAL topilmalar: 0. Bandit, Python/npm dependency va Git secret tekshiruvlari CIga kiritildi.
- Alohida lokal Compose loyihasiga DB va private fayl zaxirasi tiklandi; fayl mazmuni asl nusxa bilan solishtirildi.

Bu lokal dalillar GitHub Actions yoki haqiqiy Render deploymenti bajarilganini anglatmaydi.
