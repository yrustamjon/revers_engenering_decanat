# UniFlow — universitet xodimlari platformasi rejasi

2026-10-22 tekshiruvida topilgan xatolar, tuzatishlar va keyingi vazifalarning qabul qilish mezonlari [qolgan ishlar rejasida](REMAINING_WORK.md) qayd etilgan.

## Maqsad

Xodim ishga oid ma’lumot va bajargan ishini bir marta kiritadi. Tizim shu ma’lumotdan shaxsiy portfel va davriy hisobot tayyorlashda foydalanadi. Mas’ul xodim dalillarni ko‘rib chiqadi, aniq izoh bilan qaytaradi yoki qabul qiladi. Qog‘oz talab etiladigan jarayonda tekshirilgan nusxa chiqariladi.

TATU bu loyihada foydalanish konteksti sifatida olingan. Namuna ma’lumotlari, bo‘lim nomlari, shablonlar va tasdiqlash tartibi universitetning rasmiy bazasi yoki amaldagi ichki reglamenti hisoblanmaydi.

## Rollar

| Rol | Huquqlar |
| --- | --- |
| Xodim | O‘z profili, faoliyati, fayllari, ish rejasi va hisobotlari bilan ishlash; qaytarilgan hujjatni tuzatish |
| Tekshiruvchi | O‘z kafedrasidagi tekshiruvga yuborilgan hujjat va tegishli dalillarni ko‘rish; tasdiqlash yoki izoh bilan qaytarish |
| Administrator | Hisoblar, vakolatlar, kafedra/bo‘limlar va shablonlarni boshqarish; universitet miqyosida ko‘rib chiqish |

Xodim o‘ziga tekshiruvchi vakolatini bera olmaydi. Tekshiruvchi o‘z hisobotini tasdiqlamaydi. Administrator hisobni o‘chirish o‘rniga faolsizlantiradi; oldingi ishlar saqlanadi.

## Birinchi ishlaydigan reliz

Ushbu reliz xodim faoliyati va hisobot tizimini qamrab oladi. Uni barcha universitet jarayonlari yakunlangan mahsulot deb atash mumkin emas.

### Shaxsiy kabinet

- Profil: ism, aloqa ma’lumotlari, tarjimai hol; universitet belgilaydigan kafedra, lavozim, malaka va xodim ID.
- Portfel: maqola, konferensiya, sertifikat, o‘quv-uslubiy ish va loyiha.
- Natijaga sana, tavsif, manba havolasi yoki tasdiqlovchi fayl biriktirish.
- Ish rejasida maqsad, bajarilgan miqdor va muddat.
- Bosh sahifada haqiqiy saqlangan ma’lumotdan hisoblanadigan ko‘rsatkichlar va faoliyat dinamikasi.

### Hisobot jarayoni

1. Xodim hisobot turi va davrini belgilaydi.
2. Portfelidan tegishli ishlarni tanlaydi.
3. Qoralamani saqlaydi yoki tekshiruvga yuboradi.
4. Tizim majburiy ma’lumot va dalil mavjudligini tekshiradi.
5. Tekshiruvchi tasdiqlaydi yoki sababni yozib qaytaradi.
6. Xodim tuzatadi va qayta yuboradi.
7. Qabul qilingan hisobot arxivda saqlanadi va chop etilishi mumkin.

Tekshiruvdagi yoki tasdiqlangan hisobot va unga bog‘langan faoliyat dalillarini xodim o‘zgartira olmaydi. Harakatlar muallif va vaqt bilan tarixga yoziladi. Shablon keyin yangilansa, oldingi hisobotning shablon nusxasi saqlanadi.

Bu relizda bitta tekshiruvchi qarori mavjud. Ketma-ket bir nechta rahbarning tasdig‘i va elektron raqamli imzo alohida bosqichlardir.

### Boshqaruv va foydalanish

- Haqiqiy xodim hisobini administrator yaratadi; ochiq ro‘yxatdan o‘tish yo‘q.
- Hisoblar login/parol orqali kiradi. Parol serverda xeshlanadi va javoblarda qaytarilmaydi.
- Namunaviy xodim, tekshiruvchi va administrator kabinetlari faqat mahalliy ishlab chiqish rejimida mavjud.
- Bildirishnomalar va qidiruv.
- Telefon va kompyuterga mos navigatsiya.
- Administrator shablonlarning tavsifi, turi va versiyasini boshqaradi. Qo‘shimcha matn, batafsil matn, son, sana va havola maydonlari, majburiylik hamda server tekshiruvi mavjud. Eski hisobot tuzilmasi va qiymatlari alohida saqlanadi.

## Qabul qilish mezonlari

| Jarayon | Qachon tayyor hisoblanadi? |
| --- | --- |
| Profil | O‘zgartirish saqlanadi va sahifa qayta ochilganda qoladi; oddiy xodim lavozim/vakolatni o‘zgartirmaydi |
| Portfel | Ish yaratiladi, tahrirlanadi, dalil yuklanadi; begona foydalanuvchi faylni ocholmaydi |
| Hisobot | Yuborish → qaytarish → tuzatish → qayta yuborish → tasdiqlash brauzer orqali ishlaydi |
| Himoyalangan yozuv | Tekshiruvdagi yoki tasdiqlangan hujjat/dalilni API orqali ham o‘zgartirib bo‘lmaydi |
| Tekshiruv | Vakolatsiz foydalanuvchi qaror berolmaydi; muallif o‘zini tasdiqlay olmaydi |
| Boshqaruv | Yaratilgan haqiqiy xodim kiradi; faolsizlantirilgan xodim kira olmaydi; eski hujjatlar qoladi |
| Shablon tarixi | Yangi versiya oldingi hisobotning saqlangan shablonini o‘zgartirmaydi |
| Interfeys | Asosiy sahifalarda xato tugmalar va soxta saqlash yo‘q; telefonda menyu va shakllar ishlaydi |
| Sinov | Backend ruxsat/jarayon sinovlari, TypeScript build va asosiy brauzer sinovlari muvaffaqiyatli tugaydi |

## Universitetga moslashtirish bosqichi

Universitet mas’ullari bilan haqiqiy shakllar va tartiblar tekshiriladi. Keyingi ishlar aniq hujjatga tayangan holda bajariladi:

1. **Hisobot so‘rovlari:** mas’ul hisobot davri, shabloni, qabul qiluvchilari va muddatini belgilaydi; xodimga topshiriq tushadi. Hozir xodim o‘z hisobotini yaratadi.
2. **Ko‘p bosqichli kelishish:** qaysi hujjat kafedra, fakultet va markaziy bo‘limdan o‘tishi; ketma-ket yoki parallel bosqichlar; o‘rinbosarlik va qayta kelishish.
3. **Shakllarni kengaytirish:** shartli maydonlar, takrorlanadigan jadvallar va murakkab hisoblash qoidalari; tekshiruvchining izohini aynan maydonga bog‘lash. Asosiy dinamik maydonlar va versiyali qiymatlar joriy relizda mavjud.
4. **Jamlama hisobot:** tasdiqlangan xodim natijalaridan kafedra/fakultet kesimida takrorlarni hisobga olgan holda yig‘ish; hammuallif maqolalarini bitta ilmiy natija sifatida bog‘lash.
5. **Ishga qabul qilish:** nomzod profili, lavozimga ariza, tanlov bosqichlari va ishga qabul qilinganda ma’lumotni xodim jildiga o‘tkazish.
6. **Kadrlar hujjatlari:** shartnoma/buyruq, ish o‘zgarishi, ta’til arizasi va tegishli hujjatlar. Har bir tur uchun alohida saqlash va kirish qoidalari.
7. **Rag‘batlantirish asoslari:** tasdiqlangan natijani universitetning amaldagi mezoniga bog‘lash. Maqola yuklash avtomatik ish haqi yoki mukofot tayinlamaydi.

## Tashqi tizimlar va ishga chiqarish

- **E-IMZO:** integratsiya shartlari, imzolash vakolatlari va imzoni tekshirish jarayoni kerak. Hozirgi tizimdagi tasdiq ERI hisoblanmaydi.
- **HEMIS yoki boshqa universitet tizimi:** ruxsat etilgan API va ma’lumot egalarining roziligi bilan xodim/yuklama ma’lumotini sinxronlash. Hozir bunday ulanish yo‘q.
- **Buxgalteriya:** haq to‘lashning amaldagi qoidalari va ruxsat etilgan interfeys bo‘yicha tasdiqlangan asoslarni uzatish. To‘liq oylik hisoblash joriy relizga kirmaydi.
- **Ishchi muhit:** haqiqiy domen, HTTPS, maxfiy kalitlar, PostgreSQL, himoyalangan doimiy fayl saqlash, zaxira nusxa va tiklash sinovi, kuzatuv va xatolarni qayd qilish.
- **Maxfiylik:** xodimning shaxsiy hujjatlari uchun aniq ko‘rish vakolatlari, saqlash muddati va ma’lumot bilan ishlash tartibi.

## Pilot sinov

Avval bitta kafedrada bitta hisobot turini to‘liq sinash: xodim va tekshiruvchi real shablon bo‘yicha ishlaydi. Qayerda ortiqcha kiritish, noto‘g‘ri maydon, tushunarsiz holat yoki takroriy ish borligi yoziladi. Qabul qilish mezonlari bajarilgach, boshqa bo‘limlarga kengaytiriladi.

Ish kun soni bilan emas, tekshirilgan natija bilan yuritiladi. Kodni qurish va tekshirish mavjud ish sessiyasida davom ettiriladi; bu hujjat suhbatdan tashqarida mustaqil fon xizmati ishlayotganini anglatmaydi. Universitet vakolati, integratsiya ruxsati yoki haqiqiy reglament talab qilinadigan nuqtalar ochiq qayd etiladi.
