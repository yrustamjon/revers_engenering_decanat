from django.db import migrations


def freeze_routes(apps, schema_editor):
    Report = apps.get_model('core', 'Report')
    Profile = apps.get_model('core', 'Profile')
    reports = Report.objects.filter(review_department='', status__in=['submitted', 'returned', 'approved'])
    for user_id, department in Profile.objects.filter(user_id__in=reports.values('owner_id')).values_list('user_id', 'department'):
        reports.filter(owner_id=user_id).update(review_department=department)


class Migration(migrations.Migration):
    dependencies = [('core', '0005_submission_history_and_admin_audit')]
    operations = [migrations.RunPython(freeze_routes, migrations.RunPython.noop)]
