# Windowsda mahalliy ishga tushirish

Talablar: **Python 3.12 yoki yangi**, **Node.js 22 yoki yangi**, Git va Windows PowerShell 5.1 yoki PowerShell 7. Python o‘rnatilganda Windows launcher (`py`) yoki `python.exe` PATHda, Node o‘rnatilganda `node.exe` va `npm.cmd` PATHda bo‘lsin. O‘rnatishdan so‘ng yangi terminal oching.

## Tez boshlash

PowerShellda loyiha papkasiga o‘ting. Quyidagi buyruqlarni repozitoriy ildizida bajaring:

```powershell
.\scripts\setup.ps1 -Demo
.\scripts\dev.ps1
```

Brauzerda **http://127.0.0.1:5173** ni oching. Terminal ochiq tursin; `Ctrl+C` shu skript boshlagan ikkala xizmatni to‘xtatadi. 8000 yoki 5173 porti band bo‘lsa, skript boshqa jarayonni to‘xtatmaydi va boshqa portni yashirincha tanlamaydi. Band portdagi oldingi dev xizmatini uning terminalidan to‘xtating.

`setup.ps1` virtual muhit yaratadi, Python va frontend paketlarini o‘rnatadi, migratsiya, frontend build va Django tekshiruvini bajaradi. `-Demo` namuna hisoblar va hujjatlarni qo‘shadi. Ularni qayta seed qilish mavjud tahrirlarni saqlaydi. Virtual muhitni faollashtirish shart emas.

Agar PowerShell `running scripts is disabled` desa, faqat shu terminal sessiyasi uchun:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\setup.ps1 -Demo
.\scripts\dev.ps1
```

Bu mashinaning doimiy siyosatini o‘zgartirmaydi. Tashkilot siyosati skriptlarni taqiqlagan bo‘lsa, quyidagi alohida terminal buyruqlaridan foydalaning yoki administrator belgilagan tartibga amal qiling.

## Xizmatlarni alohida boshlash

Birinchi terminalda, loyiha ildizidan:

```powershell
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000 --noreload
```

Ikkinchi terminalda, loyiha ildizidan:

```powershell
npm.cmd run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

Har birini o‘z terminalida `Ctrl+C` bilan to‘xtating.

## Namunasiz hisob va tekshiruvlar

Haqiqiy mahalliy hisob bilan boshlash uchun `setup.ps1` ni `-Demo`siz bajaring, keyin birinchi administratorni yarating:

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\python.exe backend/manage.py createsuperuser
```

Tekshiruvlar:

```powershell
.\.venv\Scripts\python.exe backend/manage.py test core --verbosity 2
npm.cmd run build --prefix frontend
```

Brauzer sinovlari uchun Chromium o‘rnating va ikkala xizmat ishlayotgan namuna muhitida sinovlarni bajaring:

```powershell
Set-Location frontend
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Sinovlar namuna bazasiga yozuvlar yaratadi; haqiqiy xodimlar ma’lumotlari bor bazada bajarmang.

## Chegaralar

Bu yo‘l mahalliy React/Django ishlab chiqish muhiti uchun. Ishchi server uchun [joylashtirish qo‘llanmasi](DEPLOYMENT.md) dagi PostgreSQL, HTTPS va zaxira tartibi kerak. `.venv`, baza, yuklangan hujjatlar, `.env` va tokenlar Gitga kiritilmaydi.

Telegram orqali Codex topshiriqlarini bajaruvchi xizmat va uning integratsion sinovlari Linuxdagi jarayon nazorati (`fcntl`, `/proc`, signallar) bilan qurilgan; ular native Windowsda ishlashga mo‘ljallanmagan. Ularni alohida Linux host yoki WSL2 muhitida bajaring; [Telegram qo‘llanmasi](TELEGRAM_ASSISTANT.md) dagi haqiqiy model kirishi va xizmat talablari ham bajarilishi kerak. Web ilovani Windowsda ishga tushirish bu xizmatni avtomatik faollashtirmaydi.

**Tekshiruv chegarasi:** ushbu skriptlar Linux cloud muhitida yozilgan; haqiqiy Windows/PowerShellda o‘rnatish, `Ctrl+C` bilan yopish va port to‘qnashuvi sinovi hali bajarilmagan.
