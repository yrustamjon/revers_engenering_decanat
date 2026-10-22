# UniFlow DevSecOps

## Tekshiruv zanjiri

`.github/workflows/ci.yml` push, PR va qo‘lda ishga tushirishni qo‘llaydi. Standart token vakolati `contents: read`; actionlar commit SHA bilan, scanner va asosiy application image’lar digest bilan tanlangan. Registry credentiallari image ichiga ko‘chirilmaydi.

1. SQLite backend, migratsiya tekshiruvi va Telegramning offline testlari.
2. TypeScript/build va parol bilan kiruvchi brauzer sinovlari: login, noto‘g‘ri parol, reload, logout, sessiya tugashi, vakolatlar va hisobot aylanishi.
3. Haqiqiy PostgreSQL/Redis bilan backend testlari; alohida jarayonlar cache hisoblagichini ulashishi tekshiriladi.
4. Bandit SAST (medium/high), `pip-audit` (barcha ma’lum dependency zaifliklari), npm audit (high/critical gate), Gitleaks (Git tarixi va ishlayotgan diff, redaction yoqilgan).
5. Yuqoridagilar o‘tgach non-root application image yig‘iladi. Dependency mosligi buildda `pip check` bilan tekshiriladi; runtime’dan pip/setuptools/wheel va ensurepip olib tashlanadi.
6. Shu image bilan alohida PostgreSQL/Redis ishga tushiriladi: React/assets, readiness, private media, haqiqiy admin/login/CSRF/logout va demo yo‘li yo‘qligi tekshiriladi.
7. Trivy image zaifliklarini tekshiradi va CycloneDX SBOM beradi. **HIGH/CRITICAL topilsa gate yiqiladi; `ignore-unfixed` va umumiy ignore ro‘yxati yo‘q.**
8. Qo‘lda `workflow_dispatch` ishga tushirilganda, barcha gatelar o‘tgach commitga bog‘langan image arxivi va `SHA256SUMS` release artifact sifatida beriladi. Hisobotlar alohida saqlanadi. Avtomatik production deploy yoki registry publish yoqilmagan.

Dependabot Python, npm, Docker va action yangilanishlariga haftalik PR tayyorlaydi. Scanner va base digestlarini yangilash ham gate orqali o‘tishi kerak. SBOM/checksum signed provenance o‘rnini bosmaydi; GitHub branch protection va required checks’ni repo egasi server sozlamalarida yoqadi. Workflow faylining o‘zi branch protectionni yoqmaydi.

## Lokal tekshiruv

```bash
python3 -m venv .local/security-venv
.local/security-venv/bin/pip install -r requirements-security.txt
bash scripts/security-check.sh
```

Docker va Node/npm kerak. Credential qiymatlari buyruq argumentiga berilmaydi. Hisobotlar Gitga kirmaydigan `artifacts/security/` ichida bo‘ladi. Gitleaks konteyneri tarmoqsiz ishlaydi. Python advisory so‘rovi rasmiy PyPI xizmatidan foydalanadi.

```bash
docker build -f Dockerfile.render -t uniflow:review .
bash scripts/container-smoke.sh uniflow:review
```

Smoke skript alohida tarmoq va tasodifiy credentiallar yaratadi; tashqi port ochmaydi, yakunda o‘z konteynerlarini olib tashlaydi. Haqiqiy xodimlar bazasida ishlamaydi. `UNIFLOW_SMOKE_RUN_TESTS=1` qo‘shilsa image ichidagi backend testlari ham PostgreSQL bilan bajariladi.

Cloud proxy ortida build uchun ishonchli CA BuildKit secret orqali beriladi. Buildx holatini workspace ichida saqlash mumkin; Docker authentication konfiguratsiyasi o‘zgartirilmaydi:

```bash
BUILDX_CONFIG="$PWD/.local/buildx" docker build -f Dockerfile.render \
  --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t uniflow:review .
```

TLS va proxy himoyasi o‘chirilmaydi. Trivy DB rasmiy `ghcr.io/aquasecurity/trivy-db:2` registridan olinadi. Yangi advisory bazasi keyingi tekshiruv natijasini o‘zgartirishi mumkin; bir marta yashil bo‘lish doimiy kafolat emas.

## Release va production

- [Render](RENDER.md) yoki [Compose](DEPLOYMENT.md) ko‘rsatmasi bilan tekshirilgan commit/image’dan boshlang.
- Secretlarni secret manager yoki Gitga kirmaydigan `0600` faylda saqlang; bootstrap admin parolini hisob yaratilgach olib tashlang.
- DEBUG yopiq, alohida PostgreSQL/Redis, HTTPS va private durable media ishlatilsin. App non-root foydalanuvchida ishlaydi; DB/Redis portlari tashqariga ochilmaydi.
- `/healthz` DB va cachega murojaat qiladi; nosozlikda infratuzilma tafsilotisiz 503 qaytaradi. Gunicorn access/error loglari stdout/stderrga chiqadi; log yig‘ish va alert manzilini hostda sozlang. Login paroli/request body logga chiqarilmaydi.
- Login va API throttlelari umumiy client-IP funksiyasini ishlatadi. Faqat `DJANGO_TRUSTED_PROXY_CIDRS` dagi haqiqiy proxy manzillaridan kelgan `X-Forwarded-For` qabul qilinadi; boshqa sarlavha e’tiborsiz qoldiriladi. `DJANGO_TRUST_PROXY=1` HTTPS scheme uchun alohida sozlama. CIDRni haqiqiy edge topologiyasi bo‘yicha kiriting; `0.0.0.0/0` qo‘ymang.
- Har release oldidan DB/media zaxirasi olinadi. Kod rollbacki faqat yangi sxema bilan mos bo‘lsa qilinadi; sxema mos bo‘lmasa kelishilgan maintenance oynasida oldingi **DB va media juftligi** tiklanadi.

## Backup va tiklash

Compose hostida:

```bash
UNIFLOW_COMPOSE_PROJECT=uniflow UNIFLOW_ENV_FILE=.env \
  bash scripts/backup.sh --run .local/backups/release-001
```

Skript qisqa maintenance oynasida backendni to‘xtatadi, PostgreSQL custom dump va private media arxivini oladi, SHA-256 manifest yozadi, backendni qayta boshlaydi. Mavjud backup papkasiga yozmaydi; `umask 077`. Compose override ishlatilsa `UNIFLOW_COMPOSE_OVERRIDE` yo‘lini bering. Backupning o‘zi ham shaxsiy hujjat: uni shifrlangan alohida saqlashga ko‘chiring, saqlash muddatini belgilang. Ishlayotgan deploy/migratsiya bilan bir vaqtda backup boshlamang.

Tiklash avval **yangi alohida Compose project** va bo‘sh DB/volume’da bajariladi:

1. `manifest.json` dagi DB/media checksumlarini tekshiring; arxivda absolute path, `..`, symlink yoki boshqa maxsus fayl bo‘lmasin.
2. Yangi project’da faqat DB/Redisni boshlang. Birlamchi DB va volume’larni target qilmang.
3. `pg_restore --no-owner --no-privileges --exit-on-error` bilan dumpni bo‘sh DBga tiklang.
4. Shu project’ning yangi private-media volume’iga tekshirilgan arxivni tiklang.
5. Backupga mos image’ni boshlang; readiness, hisobotlar va faylning asl mazmuni/hashini solishtiring.
6. Qabul qilingach host operatori production cutover qiladi. Sinovdan o‘tmagan tiklashni to‘g‘ridan-to‘g‘ri production ustiga bajarmang.

Render-managed DB/disk uchun platformaning backup/export/tiklash tartibi ham aynan ishlatiladigan tarifda tekshiriladi; lokal Compose mashqi Render snapshotini tasdiqlamaydi.

## Hozirgi tekshiruv chegarasi

Lokal testlar, konteyner build/scanner, izolyatsiyalangan DB/media tiklash va CI konfiguratsiyasi alohida qayd qilinadi. GitHub Actions masofaviy run natijasi tekshirilmaguncha u o‘tdi deb yozilmaydi. Haqiqiy domen, edge IP, monitoring destination, off-host shifrlangan backup va universitet pilot qabulini host/tashkilot egasi bilan ishchi muhitda yakunlash kerak.
