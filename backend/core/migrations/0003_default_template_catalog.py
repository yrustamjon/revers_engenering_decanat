from django.db import migrations


def create_catalog(apps, schema_editor):
    Template = apps.get_model('core', 'ReportTemplate')
    definitions = [
        ('scientific-v1', 'Ilmiy faoliyat hisoboti', 'Maqolalar, konferensiyalar va ilmiy loyihalarni bir joyga jamlang.', 'scientific', ['Hisobot nomi', 'Hisobot davri', 'Ilmiy natijalar', 'Tasdiqlovchi fayl yoki havola'], 'FlaskConical'),
        ('annual-v1', 'Yillik faoliyat hisoboti', 'Yil davomida bajarilgan ishlar va erishilgan natijalar.', 'annual', ['Hisobot nomi', 'Hisobot davri', 'Bajarilgan ishlar', 'Tasdiqlovchi fayl yoki havola'], 'ChartNoAxesCombined'),
        ('teaching-v1', 'O‘quv-uslubiy hisobot', 'Darslar, o‘quv qo‘llanmalar va uslubiy ishlar hisoboti.', 'teaching', ['Hisobot nomi', 'Hisobot davri', 'O‘quv-uslubiy natijalar', 'Tasdiqlovchi fayl yoki havola'], 'BookOpen'),
        ('qualification-v1', 'Malaka oshirish hisoboti', 'Kurslar, stajirovkalar va olingan sertifikatlar.', 'qualification', ['Hisobot nomi', 'Hisobot davri', 'Malaka natijalari', 'Tasdiqlovchi fayl yoki havola'], 'Award'),
    ]
    for template_id, title, description, report_type, fields, icon in definitions:
        Template.objects.get_or_create(id=template_id, defaults={'title': title, 'description': description, 'type': report_type, 'version': '1.0', 'fields': fields, 'icon': icon, 'is_active': True})


class Migration(migrations.Migration):
    dependencies = [('core', '0002_department_reporttemplate_report_template_snapshot_and_more')]
    operations = [migrations.RunPython(create_catalog, migrations.RunPython.noop)]
