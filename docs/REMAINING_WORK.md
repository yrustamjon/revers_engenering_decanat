# UniFlow: tekshiruv natijasi va qolgan ishlar

**MVP yangilanishi:** P1-01 (yuborish nusxalari), P1-02 (tarixni saqlash), P1-04 (administrator auditi), T-02 (DB noyobligi), T-08 (demo interfeys) yopildi. P1-03 uchun hisobotning bo‘lim yo‘li muzlatiladi va rename saqlanadi; to‘liq tashkiliy FK modeli keyingi kengaytirishdir. P1-05 uchun trusted-proxy CIDR mexanizmi bor, haqiqiy edge konfiguratsiyasi hostda tekshiriladi. Quyidagi dastlabki topilmalar audit tarixi sifatida saqlangan. Joriy mezonlar: [MVP](MVP.md), [DevSecOps](DEVSECOPS.md).

Holat: **2026-10-22, Toshkent vaqti**. React interfeysi, DRF API, rollar, hujjat aylanishi, paketlar, Docker konfiguratsiyasi va Telegram kodi tekshirildi. TATUning rasmiy reglamenti va tashqi integratsiyalar tekshirilmagan.

Ishlayotgan asosiy jarayon: xodim portfelga dalil kiritadi → saqlangan shablon asosida hisobot tayyorlaydi → mas’ulga yuboradi → izoh bilan qaytariladi yoki tasdiqlanadi → tasdiqlangan hujjat arxivga tushadi. Profil, ish rejasi va administrator boshqaruvi mavjud. Umumuniversitet jarayonlari uchun quyidagi ishlar qoladi.

## Shu tekshiruvda tuzatilganlar

| Muammo | Tuzatish |
| --- | --- |
| Reviewer/adminning shaxsiy ko‘rsatkichlari va portfeliga hamkasblar yozuvlari qo‘shilgan | Dashboard, portfel, “Hisobotlarim”, tegishli belgilar va faoliyat qidiruvi `owner_id` bilan cheklangan. Tekshiruv/arxiv vakolati saqlangan. |
| Faol shablonsiz talablarsiz hisobot yaratilgan | Mos faol shablonsiz yaratish rad etiladi. Eski shablonsiz qoralamani yuborish ham bloklanadi; yangi qoralama kerak. Haqiqiy snapshot saqlagan oldingi qoralama ishlashda davom etadi. |
| PostgreSQLda `DISTINCT … FOR UPDATE` hisobot yuborishni to‘xtatgan | Vakolat so‘rovi subquery orqali yozilgan. Xodim/reviewer yuborishi haqiqiy PostgreSQLda tekshirilgan; alohida CI job qo‘shilgan. |
| Sana maydoni boshqa ISO shakllarni qabul qilgan | Sana qat’iy `YYYY-MM-DD` bo‘lishi va kalendarda mavjudligi tekshiriladi. |
| Mobil yashirin menyu fokusni olgan; yordamchi matnlar xira bo‘lgan | Yopiq menyu `inert`; ochiq menyuda fokus boshqariladi va yopilganda qaytadi. Tekshirilgan yordamchi matnlar mobil/desktopda kamida 4.5:1 kontrastga ega. |
| Eski backend paketlarida e’lon qilingan xavfsizlik tuzatishlari yetishmagan | Django **5.2.17**, DRF **3.17.2** ga yangilangan. Tekshiruv paytida ushbu aniq versiyalarning PyPI ma’lumotida advisory ko‘rsatilmagan. |
| Productiondagi workerlar login limitlarini alohida xotirada saqlagan | Umumiy Redis cache, Compose xizmati va healthcheck qo‘shilgan. Production Redis manzilisiz boshlanmaydi. Mustaqil Python jarayonlari hisoblagichni ulashishi tekshirilgan. |
| Telegram `/cancel` uzilishdan keyin takror kelib keyingi topshiriqni bekor qilishi mumkin bo‘lgan | Buyruq, aynan tanlangan topshiriq va javob bir tranzaksiyada yoziladi; keyin bekor qilish signali beriladi. Uzilish/replay regressiyalari bor. |
| Windows uchun faqat Linux buyruqlari bo‘lgan | PowerShell skriptlari va [Windows qo‘llanmasi](WINDOWS.md) qo‘shilgan. Haqiqiy Windows tekshiruvi hali qolgan. |
| Cloud proxysi lokal konteyner healthcheckiga aralashgan | Faqat konteynerning o‘z `127.0.0.1` probe so‘rovi to‘g‘ridan-to‘g‘ri bajariladi. Tashqi so‘rovlarning proxy/TLS qoidalari saqlanadi. |

## P1 — haqiqiy hujjatlar bilan pilotdan oldin

| ID | Qolgan ish va ta’siri | Qabul qilish mezoni | Asos |
| --- | --- | --- | --- |
| P1-01 | **Har yuborishning o‘zgarmas nusxasi.** Hozir tarix harakat/izoh/vaqtni saqlaydi. Qaytarilgandan keyingi tahrir sabab birinchi topshirilgan mazmunni to‘liq tiklab bo‘lmaydi. | Har yuborishga report, javoblar, faoliyat va fayl identifikatori/hash nusxasi saqlanadi; ikki versiya farqi ko‘rinadi. | [Report/History](../backend/core/models.py), [submit](../backend/core/views.py) |
| P1-02 | **Saqlash va o‘chirish qoidasi.** Qaytarilgan hisobotni o‘chirish uning tarixini ham yo‘qotadi. | Bir marta yuborilgan hisobot soft-delete/arxiv orqali saqlanadi; muddat va vakolatli yakuniy o‘chirish tartibi belgilanadi. | `perform_destroy`, `History.report` |
| P1-03 | **Tashkiliy mansublik tarixi.** Kafedra/fakultet matn, reviewer vakolati xodimning hozirgi kafedrasiga qaraydi. Ko‘chirish eski hujjat vakolatiga ham ta’sir qiladi. | Tashkiliy FKlar va topshirilgan paytdagi bo‘linma saqlanadi; ko‘chirishdan keyingi vakolat universitet qoidasi bo‘yicha sinovlanadi. | `Profile`, `reviewer_reports`, [admin API](../backend/core/admin_api.py) |
| P1-04 | **Administrator auditi.** Rol, hisob holati, bo‘lim va shablon tahririning oldingi/keyingi qiymatlari uchun alohida tarix yo‘q. | Kim/qachon/nimani/nima sababdan o‘zgartirgani saqlanadi; oddiy administrator auditni tahrirlay olmaydi. | [admin API](../backend/core/admin_api.py) |
| P1-05 | **Haqiqiy mijoz IP.** Login `REMOTE_ADDR` ni ishlatadi. Nginx ortida umumiy 100 urinish/5 daqiqa limiti barcha xodimga birga tushishi mumkin. Redis IP zanjirini tuzatmaydi. | Haqiqiy edge host/subnet bo‘yicha ishonch sozlanadi; edge mijoz sarlavhasini almashtiradi; turli mijozlar va soxta IP sarlavhasi bilan sinov o‘tadi. | `login_view`, [Nginx](../deploy/nginx.conf) |
| P1-06 | **Ishchi host va tiklash.** Haqiqiy domen/HTTPS, monitoring va DB+fayllarni zaxiradan tiklash hali tekshirilmagan. | HTTPS orqali ikki rol bilan hujjat jarayoni; zaxirani boshqa muhitga tiklash; xatoga signal; server restartidan keyin ma’lumot saqlanishi. | [Deployment](DEPLOYMENT.md) |
| P1-07 | **Haqiqiy TATU shakli va tartibi.** Namuna rasmiy reglament emas. Noto‘g‘ri shakl raqamlashtirilsa avvalgi qog‘oz muammosi takrorlanadi. | Bitta haqiqiy hisobotning maydon/dalil/davr/mas’ul/yo‘li universitet vakili bilan kelishiladi; bitta kafedrada shu shaklda pilot o‘tadi. | [Mahsulot rejasi](PRODUCT_PLAN.md) |

## P2 — universitet miqyosidagi funksiyalar

| ID | Ish | Tugallash mezoni |
| --- | --- | --- |
| P2-01 | **Hisobot so‘rovini tarqatish:** mas’ul davr/shablon/muddat/xodimlarni tanlaydi. Hozir xodim o‘zi hisobot yaratadi. | Xodim topshiriq oladi; mas’ul topshirmagan/qaytarilgan/kechikkan hisobotlarni ko‘radi. |
| P2-02 | **Ko‘p bosqichli kelishish:** kafedra → fakultet → tegishli bo‘lim, parallel qaror va o‘rinbosarlik. Hozir bitta mas’ul qarori bor. | Vakolat, navbat, qaytarish manzili va yakuniy qaror haqiqiy hujjat turiga mos ishlaydi. |
| P2-03 | **Maydonga bog‘langan izoh, shartli maydon va takroriy jadval.** Asosiy dinamik matn/son/sana/havola maydonlari mavjud. | Xodim izohdan kerakli maydonga o‘tadi; shartli majburiylik frontend/backendda bir xil. |
| P2-04 | **Kafedra/fakultet jamlamasi, Word/Excel eksporti va hammualliflik.** Hozir individual chop etish/brauzer PDF bor. | Ikki xodimdagi bitta maqola kelishilgan qoida bo‘yicha sanaladi; eksport rasmiy namuna bilan solishtiriladi. |
| P2-05 | **Nomzoddan xodimga:** ariza, CV/diplom, tanlov/suhbat, qabul natijasi. | Qabul qilingan nomzod qayta kiritilmasdan xodim jildiga o‘tadi; rad etilgan nomzod uchun saqlash qoidasi bor. |
| P2-06 | **Kadrlar jildi:** shartnoma, buyruq, stavka/lavozim tarixi, ta’til, amal muddati. Oddiy profil bularni qamramaydi. | Har tur uchun maxsus maydon, vakolat, tarix va muddat xabari ishlaydi. |
| P2-07 | **Rejani dalil bilan bog‘lash.** Hozir bajarilgan miqdor qo‘lda kiritiladi. | Band faoliyatga bog‘lanadi; tasdiqlangan natija ajratiladi; bitta dalil takror hisoblanmaydi. |
| P2-08 | **Rag‘batlantirish asosi:** tasdiqlangan natijani amaldagi mezon va davrga bog‘lash. | Mas’ul mezon versiyasi va hisobni tekshirib buxgalteriyaga tasdiqlangan asos beradi. Maqola yuklashning o‘zi oylik tayinlamaydi. |
| P2-09 | **Hisobotdan tashqari hujjat aylanishi:** xizmat xati, bildirishnoma, ariza, kiruvchi/chiquvchi hujjat reyestri va rezolyutsiya. | Ro‘yxat raqami, jo‘natuvchi/qabul qiluvchi, ijrochi/muddat, topshiriq va ijro nazorati bir hujjat kartasida kuzatiladi; har tur vakolati kelishiladi. Hozir markaziy jarayon xodim hisobotidir. |

## P2 — texnik mustahkamlash

| ID | Kamchilik | Tekshiriladigan natija |
| --- | --- | --- |
| T-01 | `workspace/` barcha vakolatli hisobot/faoliyat va tarixni birga qaytaradi; sahifalash yo‘q. | Paginated API, server qidiruvi va aggregate dashboard; haqiqiy hajmga yaqin bazada javob vaqti/query soni o‘lchanadi. |
| T-02 | Xodim ID noyobligi serializerda, kafedra nomi DBda case-sensitive tekshiriladi. | Bo‘sh qiymatlarni hisobga oladigan/case-insensitive DB constraint, integrity xatosiga to‘g‘ri javob va parallel yaratish sinovi. |
| T-03 | Faylda 20 MB/kengaytma tekshiruvi bor; jami quota, orphan tozalash va skaner yo‘q. | Quota, scanning holati, faqat ishlatilmayotgan faylni tozalash va dalilni yo‘qotmaslik sinovi. Yuklab olish hozir autentifikatsiya bilan himoyalangan. |
| T-04 | Faqat eng yangi 50 bildirishnoma keladi. | Alohida sahifalangan inbox, eski o‘qilmagan xabarlarni ochish va eslatma afzalliklari. |
| T-05 | Parol almashtirish/admin reset bor; mustaqil tiklash, SSO va MFA yo‘q. | Universitet tasdiqlagan tiklash kanali; bir martalik muddatli token; administrator uchun kuchli autentifikatsiya. |
| T-06 | Report snapshot saqlaydi, shablon katalogi joyida tahrirlanadi; eski versiya yorlig‘ini qayta ishlatish mumkin. | Alohida o‘zgarmas revision yozuvlari, noyob versiya identifikatori va katalogdan eski versiyani ochish. |
| T-07 | Yuklama, ekran o‘quvchi va haqiqiy Windows tekshiruvi tugallanmagan. | Kelishilgan foydalanuvchilar hajmi; Windows o‘rnatish/Ctrl+C; klaviatura va ekran o‘quvchi bilan asosiy jarayonlar. |
| T-08 | Haqiqiy hisobda ham ayrim matnlar TATU/namunaviy muhit deb chiqadi. | Tashkilot nomi/logo va demo belgisi konfiguratsiya bilan boshqariladi; chop etish to‘g‘ri identifikatsiyaga ega. |

## Telegram va tashqi ulanishlar

| Ish | Holati va qolgan qadam |
| --- | --- |
| **Telegramda AI bilan suhbat** | Alohida Codex CLI sessiyasi bor; bu brauzerdagi aynan shu chatning nusxasi emas. Haqiqiy model javobi/davomli suhbat tekshirilmagan. Avvalgi avtomatik ruxsat tekshiruvi loyiha kontekstini `chatgpt.com` ga yuborishni rad etgan. Ruxsat hal qilinmagani uchun jonli chaqiruv takrorlanmadi. Kerakli ruxsat va qo‘llab-quvvatlanadigan tarmoq sozlamasi bilan minimal javob → Telegram yetkazilishi → ikkinchi xabar tekshiriladi. |
| **Doimiy bot xizmati** | Cloud jarayoni 24/7 host kafolati bermaydi. Systemd namunasi haqiqiy hostda autentifikatsiya/restart/tiklash bilan tekshirilishi kerak. AI runner Linuxga bog‘liq. |
| **Bot saqlash siyosati** | Jobs/outbox/update tarixi va loglarning jami hajmi cheklanmagan. Retention/rotation, disk kuzatuvi va private holatni tiklash kerak. `/new` uzilishda takror bajarilsa oldingi sessiya metadata maydoni yo‘qolishi mumkin; idempotent reset kerak. |
| **HEMIS** | Rasmiy API, berilgan vakolat va sinxronlash qoidasi kerak. Hozir ulanish yo‘q. |
| **E-IMZO** | Integratsiya sharti, imzolovchi vakolati va imzoni tekshirish jarayoni kerak. “Tasdiqlandi” holati ERI hisoblanmaydi. |
| **Buxgalteriya** | Haq/rag‘batning amaldagi qoidalari va ruxsat etilgan interfeys kerak. To‘liq oylik hisobi yo‘q. |

## Sinov dalillari va chegaralari

- **40 backend testi haqiqiy PostgreSQL 17 va Redis 8 bilan o‘tdi**, jumladan mustaqil Python jarayonlari o‘rtasidagi umumiy cache. SQLite bilan service testi Redis bo‘lmasa o‘tkazib yuboriladi.
- **12 Playwright sinovi o‘tdi:** oltitasi haqiqiy lokal API bilan, oltitasi vakolat/klaviatura/kontrast holatlari uchun API maketi bilan.
- **67 Telegram offline sinovi o‘tdi.** Ushbu tekshiruvda jonli model yoki Telegram chaqiruvi bajarilmadi.
- Frontend production build, migratsiya tekshiruvi va `pip check` o‘tdi. `npm audit` e’lon qilingan zaiflik topmadi; backendning yangilangan aniq paketlari PyPI ma’lumoti bilan tekshirildi. Bu to‘liq xavfsizlik auditi yoki kelajakdagi advisories yo‘qligi kafolati emas.
- Docker backend/frontend obrazlari yig‘ildi; alohida sinov loyihasida PostgreSQL, Redis, backend va frontend `healthy` holatiga o‘tdi. Nginx `/healthz` va bosh sahifa 200, sessiyasiz API 401, to‘g‘ridan-to‘g‘ri `/media/` 404 qaytardi. `check --deploy` faqat ongli ravishda yoqilmagan HSTS preload ogohlantirishini ko‘rsatdi. Haqiqiy domen/HTTPS, zaxiradan tiklash, Windows, rasmiy TATU jarayoni va jonli model javobi hali tekshirilmagan.

## Bajarish tartibi

1. **Hujjatga ishonch:** P1-01/02/03/04 — yuborilgan nusxa, saqlash, mansublik va administrator auditi.
2. **Bitta haqiqiy jarayon:** P1-07 bilan bitta kafedra/shaklni kelishish; P2-01/02/03 — so‘rov, kelishish va aniq tuzatishlar.
3. **Hisobotdan natija:** P2-04/07/08 — jamlama, rejaning dalili va tekshiriladigan rag‘bat asosi.
4. **Ishchi server:** P1-05/06 va T-01/02/03/05 — IP, tiklash, hajm, fayl va hisob; pilotga chiqarish.
5. **Kengaytirish:** kadrlar jildi, nomzodlar, rasmiy tashqi integratsiyalar; keyin boshqa bo‘limlarga tarqatish.

Har bosqich tegishli qabul qilish mezoni bajarilganda tugaydi. Sayt ochilishi yoki testlar yashil bo‘lishi barcha universitet jarayonlari tugaganini anglatmaydi.
