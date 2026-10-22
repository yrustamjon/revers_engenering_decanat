# UniFlow

React + TypeScript va Django REST Framework asosidagi universitet xodimlari portfeli va hisobot MVPsi. **Haqiqiy login/parol**, sessiya, logout va administrator orqali hisob ochish bilan ishlaydi. Frontend avtomatik demo hisobga kirmaydi; rollar parolsiz almashtirilmaydi.

## Ishlaydigan jarayon

Administrator → bo‘lim va hisoblar → xodim profili/portfeli → dalilli hisobot → tekshiruvchi izohi → tuzatish va qayta yuborish → tasdiqlash → arxiv/chop etish.

- Xodim o‘z ma’lumotlarini boshqaradi; tekshiruvchi tegishli bo‘lim hisobotlarini ko‘radi; administrator hisob, bo‘lim va shablonlarni boshqaradi.
- Har yuborishning alohida nusxasi saqlanadi. Qaytarilgandan keyingi tahrir oldingi nusxa yoki dalilni almashtirmaydi. Yuborilgan hisobot tarixi o‘chirilmaydi.
- Hisobotning tekshiruv bo‘limi saqlanadi; xodim ko‘chirilganda eski hisobot boshqa bo‘limga o‘tmaydi.
- Hisob/vakolat, bo‘lim va shablon amallari administrator auditida ko‘rinadi. Parol va parol hash’i auditga yozilmaydi.
- Sessiya tugaganda login sahifasi qaytadi; API javoblari cachega saqlanmaydi. Logout eski sessiyani serverda bekor qiladi.

## Mac / Linux’da boshlash

Python **3.12+**, Node.js **22+**, npm va Git kerak. Mavjud Pythonni qayta o‘rnatish shart emas.

```bash
git clone https://github.com/yrustamjon/revers_engenering_decanat.git
cd revers_engenering_decanat
bash scripts/setup.sh
.venv/bin/python backend/manage.py createsuperuser
bash scripts/dev.sh
```

Brauzer: **http://127.0.0.1:5173**. Yaratilgan administrator login/parolini kiriting. Boshqaruvdan bo‘lim, xodim va tekshiruvchi yarating. `Ctrl+C` ikkala xizmatni to‘xtatadi. Launcher macOS standart Bash bilan ham ishlaydi.

Agar kerakli Python boshqa nom bilan o‘rnatilgan bo‘lsa:

```bash
UNIFLOW_PYTHON=python3.12 bash scripts/setup.sh
```

Windows uchun [PowerShell qo‘llanmasi](docs/WINDOWS.md) bor.

## Sinovlar

```bash
.venv/bin/python backend/manage.py test core --verbosity 2
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build --prefix frontend
python3 -m unittest discover -s integrations/tests
```

Ikkala lokal xizmat ishlayotganida, **alohida sinov bazasida**:

```bash
bash scripts/test-e2e.sh
```

Brauzer sinovlari haqiqiy parolli sinov hisoblari bilan login/logout qiladi. Ularning tasodifiy credentiallari `.local/e2e/` ichida qoladi. `seed_e2e` productionda ishlamaydi. Chromium kerak: `cd frontend && npx playwright install chromium`; cloud muhitda `/usr/bin/chromium` ham qo‘llanadi. `seed_demo` va eski `/auth/demo/` yo‘li MVPni boshlash uchun ishlatilmaydi; demo autentifikatsiya endpointi olib tashlangan.

## DevSecOps va deploy

- [MVP qabul mezonlari va tekshiruv holati](docs/MVP.md)
- [DevSecOps: CI, skanerlar, release va tiklash](docs/DEVSECOPS.md)
- [Render Web Service](docs/RENDER.md)
- [Docker Compose, PostgreSQL va HTTPS](docs/DEPLOYMENT.md)
- [API shartnomasi](docs/api-contract.md)
- [Keyingi mahsulot imkoniyatlari](docs/PRODUCT_PLAN.md)
- [Telegram integratsiyasi](integrations/README.md)

Production `DEBUG=0`, PostgreSQL, Redis, HTTPS va alohida secretlarni talab qiladi. Faylli hujjatlar uchun doimiy private storage va zaxira kerak. Render Free diski vaqtinchalik bo‘lgani sabab `Dockerfile.render` fayl yuklashni doimiy saqlash sozlanguncha o‘chiradi; havolali dalil ishlaydi. Token, `.env`, DB, yuklangan hujjat va `.local/` Gitga kiritilmaydi.

MVP bitta vakolatli tekshiruvchi qarorini amalga oshiradi. TATU rasmiy reglamenti, HEMIS, E-IMZO, buxgalteriya, ko‘p bosqichli kelishish va ishga qabul modullari alohida integratsiya/mahsulot bosqichlari. Ichki tasdiq ERI o‘rnini bosmaydi. Telegram AI suhbatining holati sayt MVPsidan alohida.
