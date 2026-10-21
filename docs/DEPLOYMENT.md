# UniFlow — ishchi serverga chiqarish

Ushbu konfiguratsiya React build, Nginx, Gunicorn/Django, PostgreSQL va umumiy Redis cache uchun tayyorlangan. Lokal ishlab chiqishdagi SQLite va demo kabinetlar ishlab chiqarish muhiti uchun ishlatilmaydi.

**2026-10-22 tekshiruvi:** backend/frontend Docker obrazlari yig‘ildi; 40 backend testi PostgreSQL 17 va Redis 8 bilan o‘tdi. Alohida sinov Compose loyihasida to‘rtala xizmat `healthy` bo‘ldi; Nginx bosh sahifasi/health, sessiyasiz API va private media chegarasi tekshirildi. Haqiqiy domen/HTTPS, ishchi host va zaxiradan tiklash hali tekshirilmagan. [Qolgan ishlar](REMAINING_WORK.md) dagi P1 shartlari haqiqiy hujjatlar bilan pilotdan oldin bajariladi.

## Tuzilma

```text
Foydalanuvchi → haqiqiy domen / HTTPS edge → host 127.0.0.1:8080
                                         └ Nginx
                                            ├ React static build
                                            ├ /api/ va /admin/ → Gunicorn/Django
                                            └ /static/ → Django static volume
                                                               ├ PostgreSQL
                                                               ├ Redis
                                                               └ private-media volume
```

Ma’lumotlar bazasi va backend portlari tashqariga chiqarilmagan. `private-media` faqat backendga ulangan; Nginx `/media/` manzilini ochmaydi. Faylni olishda sessiya va foydalanuvchi vakolati API orqali tekshiriladi.

Redis ham tashqariga port chiqarmaydi; login va DRF urinish hisoblagichlari barcha workerlar uchun umumiy. Compose `DJANGO_REDIS_URL=redis://cache:6379/0` ni beradi; boshqa joylashtirishda haqiqiy manzilni kiriting. Redisda hujjat yoki asosiy sessiya saqlanmaydi; uning restarti urinish hisoblagichlarini yangilaydi. `noeviction` to‘lib qolgan cache yozuvlarini jim o‘chirib yubormaydi; cache xotirasi va xatolari kuzatilishi kerak.

## Kerakli konfiguratsiya

Ishchi hostda Docker Engine va Compose plugin, domen, HTTPS sertifikatli oldingi reverse proxy va doimiy disk bo‘lishi kerak. Maxfiy qiymatlarni secret manager orqali kiriting yoki faqat egasi o‘qiy oladigan, Gitga kirmaydigan `.env` faylida saqlang. Namunada haqiqiy kalit yoki parol yo‘q.

```sh
cp deploy/production.env.example .env
chmod 600 .env
```

Faylni xavfsiz muharrirda to‘ldiring:

| O‘zgaruvchi | Talab |
| --- | --- |
| `DJANGO_SECRET_KEY` | Shu muhit uchun alohida kriptografik tasodifiy kalit; chat yoki Gitga yozilmaydi |
| `DJANGO_ALLOWED_HOSTS` | Haqiqiy host nomi, masalan `uniflow.university.uz`; sxema yoki yo‘l kiritilmaydi |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | To‘liq HTTPS origin, masalan `https://uniflow.university.uz` |
| `POSTGRES_DB` | Ma’lumotlar bazasi nomi |
| `POSTGRES_USER` | Ilova bazasi foydalanuvchisi |
| `POSTGRES_PASSWORD` | Alohida kuchli parol |

Bir nechta host/origin vergul bilan ajratiladi. Host va origin qiymatlari oldingi HTTPS reverse proxy saqlaydigan domen bilan mos bo‘lishi kerak. Compose bo‘sh qiymatlar bilan ishga tushmaydi.

## HTTPS va proxy ishonchi

Compose Nginx portini faqat `127.0.0.1:8080` ga bog‘laydi. Uni bevosita Internetga ochmang. Hostdagi Nginx, Caddy yoki yuk taqsimlagich haqiqiy domen uchun TLSni tugatib, so‘rovni shu loopback manzilga yuborishi va `Host` sarlavhasini saqlashi kerak. HTTP tashqi so‘rovlar HTTPSga yo‘naltiriladi.

Ichki Nginx `X-Forwarded-Proto` ni **o‘zi `https` qilib qayta yozadi**; mijoz bergan qiymatga ishonmaydi. Django `DJANGO_TRUST_PROXY=1` orqali faqat ushbu joylashuvga ishonadi. Backend portini tashqariga chiqarish ushbu ishonch modelini buzadi.

Bu konfiguratsiyada secure cookie va HTTPS tekshiruvlari faol. Oddiy `http://127.0.0.1:8080` orqali kirish ishlab chiqarish loginini tekshirish usuli emas: secure cookie yuborilmaydi va CSRF origin mos kelmaydi. HTTPda mahalliy ishlab chiqish uchun `scripts/dev.sh` dan foydalaning; production himoyalarini o‘chirmang.

Compose ichidagi PostgreSQL aloqasi faqat ilova Docker tarmog‘i doirasida bo‘lgani uchun `POSTGRES_SSLMODE=disable`. Boshqa hostdagi boshqariladigan bazaga ko‘chirilsa, host, port va CA trustni sozlab `POSTGRES_SSLMODE=verify-full` qo‘llang; DB xizmatining rasmiy ko‘rsatmasiga amal qiling.

## Build va boshlang‘ich hisob

Repozitoriy ildizidan:

```sh
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose exec backend python manage.py createsuperuser
```

`compose config` ning odatiy to‘liq chiqishini umumiy logga yubormang: unda environment qiymatlari ko‘rinishi mumkin. Yuqorida faqat `--quiet` tekshiruv berilgan.

TLSni tekshiradigan cloud proxy orqali build qilinsa, uning ishonchli umumiy CA bundle faylini BuildKit secret sifatida bering. Sertifikat image qatlamiga ko‘chirilmaydi; TLS tekshiruvi o‘chirilmaydi:

```sh
UNIFLOW_BUILD_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt docker compose -f compose.yaml -f deploy/compose.proxy.yaml build
```

Bu qo‘shimcha fayl faqat proxy talab qiladigan build uchun; oddiy hostda odatiy build yetarli.

Backend boshlanishida migratsiya va `collectstatic` bajariladi. Demo seed ishlamaydi. Superuser orqali yangi xodim, tekshiruvchi, bo‘lim va haqiqiy shablonlar yaratiladi. Ishchi hisoblar va shakllarni kiriting; demo ma’lumotlarni haqiqiy ma’lumot deb ko‘chirmang.

## Tayyorlikni tekshirish

**Mijoz IP sharti:** hozir login `REMOTE_ADDR` ni hisoblaydi. Nginx ortida bu barcha xodim uchun umumiy proxy manzili bo‘lishi mumkin. Haqiqiy edge/subnet asosida IP ishonch zanjiri va mijoz sarlavhasini almashtirish sozlanib, turli IP hamda soxta header sinovi bajarilmaguncha ushbu joylashtirishni ko‘p foydalanuvchiga tayyor deb hisoblamang. Tasodifiy `X-Forwarded-For` qiymatiga ishonish yechim emas.

```sh
curl --fail http://127.0.0.1:8080/healthz
docker compose exec backend python manage.py check --deploy
```

`/healthz` Nginx ishlayotganini tekshiradi; Compose backend probe esa PostgreSQLga `SELECT 1`, Redisga `PING` va Gunicornning sessiya endpointiga javobini tekshiradi. Bular hujjat jarayoni yoki DB zaxirasini to‘liq tekshirmaydi. `check --deploy` dagi HSTS preload ogohlantirishi domenni brauzerlarning doimiy preload ro‘yxatiga kiritish uchun alohida qaror kerakligini bildiradi; uni faqat tekshiruvni jim qilish uchun yoqmang.

Haqiqiy HTTPS domen orqali quyidagilar bajarilsin:

1. Administrator va ikki alohida xodim hisobi bilan kirish.
2. Faylli faoliyat yaratish, hisobot yuborish, boshqa xodimning fayliga ruxsat yo‘qligini tekshirish.
3. Tekshiruvchi izohi bilan qaytarish, muallif tuzatishi va yakuniy tasdiq.
4. Tasdiqlangan hujjat va dalilni o‘zgartirishga server yo‘l qo‘ymasligini tekshirish.
5. Sahifa qayta ochilganda ma’lumot saqlanganini tekshirish.

## Saqlash, zaxira va yangilash

Uchta nomlangan volume bor: `database-data`, `private-media`, `django-static`. `docker compose down` ularni saqlaydi; `down -v` ma’lumotlarni olib tashlaydi. Ishchi tizimda `-v` ishlatmang.

PostgreSQL zaxirasini `pg_dump` bilan, private-media fayllarini esa shu davrga mos nusxada xavfsiz saqlang. Zaxira ham shaxsiy hujjatlarni o‘z ichiga oladi. Nusxa olish siyosati va alohida hostga tiklash mashqi amalda tekshirilishi kerak. Static fayllar builddan qayta yaratiladi.

Yangilashdan oldin DB va fayllarning tiklanadigan nusxasini oling. So‘ng kodni yangilang, obrazlarni qayta build qiling va `docker compose up -d` bajaring. Bu kichik joylashtirish uchun mo‘ljallangan; bir nechta replika va uzilishsiz migratsiya alohida release jarayonini talab qiladi.

Django loglari stdoutga yoziladi. Markaziy log, kuzatuv, fayl antivirus tekshiruvi, SMTP/parolni qayta tiklash, tashqi SSO va kengaytirilgan auditni universitetning talabiga qarab sozlash kerak. E-IMZO, HEMIS va buxgalteriyaga ulanish ushbu Docker konfiguratsiyasining o‘zi bilan paydo bo‘lmaydi.
