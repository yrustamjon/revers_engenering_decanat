from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Activity, Attachment, Department, History, Notification, Report, ReportTemplate, WorkItem
from core.templates import REPORT_TEMPLATES


class Command(BaseCommand):
    help = 'Create illustrative local demo data without overwriting existing work.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo ma’lumotlarini faqat DEBUG rejimida yarating.')
        for definition in REPORT_TEMPLATES:
            definition = dict(definition)
            template_id = definition.pop('id')
            ReportTemplate.objects.get_or_create(id=template_id, defaults=definition)
        for name, faculty, head_name in [
            ('Dasturiy injiniring kafedrasi', 'Dasturiy injiniring fakulteti', 'Dilshod Rahimov'),
            ('Kompyuter tizimlari kafedrasi', 'Kompyuter injiniringi fakulteti', ''),
            ('Axborot xavfsizligi kafedrasi', 'Kiberxavfsizlik fakulteti', ''),
        ]:
            Department.objects.get_or_create(name=name, defaults={'faculty': faculty, 'head_name': head_name})
        User = get_user_model()
        employee, employee_created = User.objects.get_or_create(username='demo_employee', defaults={'first_name': 'Azizbek', 'last_name': 'Karimov', 'email': 'azizbek.karimov@example.com'})
        reviewer, reviewer_created = User.objects.get_or_create(username='demo_reviewer', defaults={'first_name': 'Dilshod', 'last_name': 'Rahimov', 'email': 'dilshod.rahimov@example.com'})
        administrator, administrator_created = User.objects.get_or_create(username='demo_administrator', defaults={'first_name': 'Madina', 'last_name': 'Usmonova', 'email': 'madina.usmonova@example.com', 'is_staff': True})
        for user, created, role, position in [(employee, employee_created, 'employee', 'Katta o‘qituvchi'), (reviewer, reviewer_created, 'reviewer', 'Kafedra mudiri'), (administrator, administrator_created, 'administrator', 'Tizim administratori')]:
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password'])
                p = user.profile
                p.role = role
                p.phone = '+998 90 123 45 67' if role == 'employee' else '+998 91 234 56 78'
                p.department = 'Dasturiy injiniring kafedrasi'
                p.faculty = 'Dasturiy injiniring fakulteti'
                p.position = position
                p.degree = 'Texnika fanlari bo‘yicha PhD'
                p.bio = 'Dasturiy injiniring, sun’iy intellekt va ta’lim texnologiyalari yo‘nalishida faoliyat yuritaman. Ushbu profil namoyish uchun yaratilgan.'
                p.employee_id = {'employee': 'TATU-0248', 'reviewer': 'TATU-0106', 'administrator': 'TATU-0001'}[role]
                p.experience_years = 7 if role == 'employee' else 14
                p.save()
        for report in employee.reports.filter(template_version=''):
            initial_template = next((t for t in REPORT_TEMPLATES if t['type'] == report.type), None)
            if initial_template:
                report.template_version = initial_template['version']
                report.template_snapshot = dict(initial_template)
                report.save(update_fields=['template_version', 'template_snapshot'])
        if not employee_created:
            self.stdout.write('Demo foydalanuvchilar mavjud. Saqlangan ishlar o‘zgartirilmadi.')
            return
        today = timezone.localdate()
        activities = []
        examples = [
            ('Ta’limda sun’iy intellekt: individual o‘qitish yondashuvlari', 'article', 3, 'Universitet ta’limida moslashuvchan o‘qitish tizimlarini qo‘llash bo‘yicha ilmiy maqola.'),
            ('Python asoslari: amaliy mashg‘ulotlar to‘plami', 'teaching', 8, 'Dasturlash fanidan 12 ta amaliy mashg‘ulot uchun uslubiy material.'),
            ('AI & Digital Education xalqaro konferensiyasi', 'conference', 12, 'Ta’limda raqamli texnologiyalar mavzusida taqdimot bilan qatnashish.'),
            ('Machine Learning Specialization', 'certificate', 19, 'Mashinali o‘rganish algoritmlari va amaliy modellar bo‘yicha kurs.'),
            ('Universitet elektron kutubxonasi prototipi', 'project', 25, 'Talabalar bilan birgalikda qidiruv va katalog modulini ishlab chiqish.'),
            ('Mikroxizmatlar arxitekturasida ma’lumotlar xavfsizligi', 'article', 32, 'Taqsimlangan tizimlarda autentifikatsiya va ruxsatlarni boshqarish tahlili.'),
            ('Web dasturlash fanidan elektron o‘quv qo‘llanma', 'teaching', 38, 'React va Django yordamida web ilovalar yaratish bo‘yicha qo‘llanma.'),
            ('Digital Skills: zamonaviy ta’lim metodlari', 'certificate', 48, 'Raqamli ta’lim vositalari bo‘yicha malaka oshirish sertifikati.'),
            ('Talabalar ilmiy loyihalariga mentorlik', 'project', 55, 'Uchta talaba jamoasiga loyiha tuzish va ishlab chiqishda rahbarlik.'),
        ]
        for i, (title, category, days, description) in enumerate(examples):
            content = ContentFile(f'UNIFLOW — NAMOYISH UCHUN\n\n{title}\n\n{description}\n\nBu fayl haqiqiy akademik natijani tasdiqlamaydi. Faqat dastur imkoniyatlarini sinash uchun.\n'.encode('utf-8'))
            attachment = Attachment(owner=employee, name=f'namuna-{i + 1}.txt', size=content.size)
            attachment.file.save(attachment.name, content, save=True)
            activities.append(Activity.objects.create(owner=employee, title=title, category=category, date=today - timedelta(days=days), description=description, status='verified' if i in [3, 6, 7] else 'draft', attachment=attachment))
        report_specs = [
            ('III chorak ilmiy faoliyat hisoboti', 'scientific', f'{today.year}-yil · III chorak', 'returned', [0, 2, 5], 'Maqolalar bo‘limida nashr nomi va jurnal sonini aniqlashtiring. Ilovadagi ma’lumotlar bilan solishtirib qayta yuboring.', today + timedelta(days=3)),
            ('O‘quv-uslubiy ishlar hisoboti', 'teaching', f'{today.year}/{today.year + 1} o‘quv yili · I semestr', 'submitted', [1], '', today + timedelta(days=7)),
            ('Yillik faoliyat hisoboti', 'annual', f'{today.year}-yil', 'draft', [0, 1, 2, 4, 8], '', today + timedelta(days=15)),
            ('Malaka oshirish natijalari', 'qualification', f'{today.year}-yil · II yarim yillik', 'approved', [3, 7], 'Sertifikatlar va natijalar ko‘rib chiqildi. Hisobot qabul qilindi.', today - timedelta(days=5)),
        ]
        reports = []
        for title, report_type, period, report_status, indices, comment, due_date in report_specs:
            template = next(t for t in REPORT_TEMPLATES if t['type'] == report_type)
            report = Report.objects.create(owner=employee, title=title, type=report_type, period=period, status=report_status, comment=comment, due_date=due_date, submitted_at=timezone.now() - timedelta(days=2) if report_status != 'draft' else None, template_version=template['version'], template_snapshot=template)
            report.activities.set([activities[i] for i in indices])
            History.objects.create(report=report, actor=employee, action='created', comment='Hisobot qoralamasi yaratildi.')
            if report_status != 'draft':
                History.objects.create(report=report, actor=employee, action='submitted', comment='Hisobot tekshiruvga yuborildi.')
            if report_status in ['approved', 'returned']:
                History.objects.create(report=report, actor=reviewer, action=report_status, comment=comment)
            reports.append(report)
        for title, category, target, completed, days in [
            ('Ilmiy maqolalar nashr etish', 'article', 4, 2, 72),
            ('O‘quv-uslubiy materiallar tayyorlash', 'teaching', 3, 2, 35),
            ('Malaka oshirish kurslarida qatnashish', 'certificate', 2, 2, 45),
            ('Ilmiy konferensiyalarda ishtirok etish', 'conference', 3, 1, 60),
            ('Talabalar loyihalariga rahbarlik', 'project', 4, 2, 50),
        ]:
            WorkItem.objects.create(owner=employee, title=title, category=category, target=target, completed=completed, due_date=today + timedelta(days=days))
        Notification.objects.create(owner=employee, report=reports[0], title='Hisobot tuzatishga qaytarildi', message='III chorak ilmiy faoliyat hisobotingizga izoh qoldirildi. Tuzatish uchun 3 kun bor.')
        Notification.objects.create(owner=employee, report=reports[3], title='Hisobotingiz tasdiqlandi', message='Malaka oshirish natijalari qabul qilindi. Yakuniy nusxani hisobot sahifasidan ko‘rishingiz mumkin.')
        Notification.objects.create(owner=employee, title='Ish rejangizni tekshiring', message='Yil yakuni yaqinlashmoqda. Bajarilgan ishlaringizni portfelga kiritib boring.')
        Notification.objects.create(owner=reviewer, report=reports[1], title='Yangi hisobot tekshiruvga keldi', message='Azizbek Karimovning o‘quv-uslubiy hisoboti ko‘rib chiqishingizni kutmoqda.')
        self.stdout.write(self.style.SUCCESS('Demo ma’lumotlari yaratildi. Barcha profillar va dalillar namoyish uchun.'))
