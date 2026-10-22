import json
import tempfile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from .models import Activity, AuditEvent, Department, History, Report, Submission


class RealMVPTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.media.name)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.users = {}
        Department.objects.create(name='Software', faculty='Engineering')
        Department.objects.create(name='Other', faculty='Other faculty')
        for name, role, department in [('worker', 'employee', 'Software'), ('reviewer', 'reviewer', 'Software'), ('outsider', 'reviewer', 'Other'), ('admin', 'administrator', 'Software')]:
            user = get_user_model().objects.create_user(name, password='Compass!Larch92River')
            user.profile.role, user.profile.department = role, department
            user.profile.save()
            self.users[name] = user
        self.client = APIClient()
        self.client.force_authenticate(self.users['worker'])
        self.activity = Activity.objects.create(owner=self.users['worker'], title='Original evidence', description='Original content', category='article', date='2026-10-01', link='https://example.com/article')
        response = self.client.post('/api/reports/', {'title':'Original report','period':'2026','type':'scientific','activity_ids':[self.activity.pk]}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.report_id = response.data['id']

    def submit(self):
        self.client.force_authenticate(self.users['worker'])
        response = self.client.post(f'/api/reports/{self.report_id}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def return_report(self):
        self.client.force_authenticate(self.users['reviewer'])
        response = self.client.post(f'/api/reports/{self.report_id}/review/', {'decision':'returned','comment':'Please clarify the publication details.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.users['worker'])

    def test_each_submission_preserves_its_report_and_evidence(self):
        original = self.submit()['submissions'][0]['snapshot']
        self.return_report()
        self.assertEqual(self.client.patch(f'/api/activities/{self.activity.pk}/', {'title':'Corrected evidence','description':'Corrected content'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/reports/{self.report_id}/', {'title':'Corrected report'}, format='json').status_code, 200)
        response = self.submit()
        self.assertEqual([r['number'] for r in response['submissions']], [1,2])
        self.assertEqual(response['submissions'][0]['snapshot'], original)
        self.assertEqual(original['activities'][0]['description'], 'Original content')
        self.assertEqual(response['submissions'][1]['snapshot']['activities'][0]['description'], 'Corrected content')
        self.return_report()
        self.assertEqual(self.client.delete(f'/api/reports/{self.report_id}/').status_code, 400)
        self.assertEqual(Submission.objects.filter(report_id=self.report_id).count(), 2)
        self.assertTrue(History.objects.filter(report_id=self.report_id, action='submitted').exists())

    def test_employee_transfer_does_not_transfer_existing_report_authority(self):
        self.submit()
        worker = self.users['worker']
        worker.profile.department = 'Other'
        worker.profile.save()
        self.client.force_authenticate(self.users['outsider'])
        self.assertEqual(self.client.get(f'/api/reports/{self.report_id}/').status_code, 404)
        self.return_report()
        self.submit()
        self.client.force_authenticate(self.users['reviewer'])
        self.assertEqual(self.client.post(f'/api/reports/{self.report_id}/review/', {'decision':'approved'}, format='json').status_code, 200)

    def test_historical_attachment_remains_available_only_to_authorized_reviewers(self):
        response = self.client.post('/api/attachments/', {'file':SimpleUploadedFile('original.txt',b'Original evidence')}, format='multipart')
        self.assertEqual(response.status_code, 201)
        attachment_id, url = response.data['id'], response.data['url']
        self.client.patch(f'/api/activities/{self.activity.pk}/', {'attachment_id':attachment_id}, format='json')
        self.submit()
        self.return_report()
        self.client.patch(f'/api/activities/{self.activity.pk}/', {'attachment_id':None}, format='json')
        self.client.force_authenticate(self.users['reviewer'])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_authenticate(self.users['outsider'])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_changes_are_audited_without_passwords(self):
        self.client.force_authenticate(self.users['admin'])
        response = self.client.patch(f"/api/admin/users/{self.users['worker'].pk}/", {'password':'Another!Birch39Forest','is_active':False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        event = AuditEvent.objects.get(resource='user', object_id=str(self.users['worker'].pk))
        self.assertEqual(event.before['is_active'], True)
        self.assertEqual(event.after['is_active'], False)
        self.assertEqual(event.after['password_changed'], True)
        encoded = json.dumps(event.after)
        self.assertNotIn('Another!Birch39Forest', encoded)
        self.assertNotIn('pbkdf2_', encoded)
        self.assertEqual(self.client.get('/api/admin/audit/').status_code, 200)
        self.assertEqual(self.client.post('/api/admin/audit/', {}, format='json').status_code, 405)
        self.client.force_authenticate(self.users['reviewer'])
        self.assertEqual(self.client.get('/api/admin/audit/').status_code, 403)

    def test_department_rename_preserves_review_route(self):
        self.submit()
        department = Department.objects.get(name='Software')
        self.client.force_authenticate(self.users['admin'])
        self.assertEqual(self.client.patch(f'/api/admin/departments/{department.pk}/', {'name':'New Software'}, format='json').status_code, 200)
        self.users['reviewer'].profile.refresh_from_db()
        self.client.force_authenticate(self.users['reviewer'])
        self.assertEqual(self.client.get(f'/api/reports/{self.report_id}/').status_code, 200)
        self.assertEqual(Report.objects.get(pk=self.report_id).review_department, 'New Software')

    def test_real_login_logout_and_previous_session_invalidation(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.get('/api/auth/session/').status_code, 401)
        token = client.cookies['csrftoken'].value
        response = client.post('/api/auth/login/', {'username':'worker','password':'Compass!Larch92River'}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        previous_session = client.cookies['sessionid'].value
        self.assertEqual(client.get('/api/workspace/')['Cache-Control'], 'private, no-store')
        self.assertEqual(client.post('/api/auth/logout/', {}, format='json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 204)
        self.assertEqual(client.get('/api/workspace/').status_code, 403)
        attacker = APIClient()
        attacker.cookies['sessionid'] = previous_session
        self.assertEqual(attacker.get('/api/workspace/').status_code, 403)
        self.assertEqual(client.post('/api/auth/demo/', {'role':'administrator'}, format='json').status_code, 404)

    @override_settings(TRUSTED_PROXY_CIDRS=['10.10.0.0/24'])
    def test_only_trusted_proxies_can_supply_client_address(self):
        from django.test import RequestFactory
        from .security import client_ip
        factory = RequestFactory()
        untrusted = factory.get('/', REMOTE_ADDR='198.51.100.9', HTTP_X_FORWARDED_FOR='192.0.2.3')
        trusted = factory.get('/', REMOTE_ADDR='10.10.0.2', HTTP_X_FORWARDED_FOR='192.0.2.3, 10.10.0.1')
        malformed = factory.get('/', REMOTE_ADDR='10.10.0.2', HTTP_X_FORWARDED_FOR='spoofed')
        self.assertEqual(client_ip(untrusted), '198.51.100.9')
        self.assertEqual(client_ip(trusted), '192.0.2.3')
        self.assertEqual(client_ip(malformed), '10.10.0.2')

    def test_employee_number_uniqueness_is_enforced_by_database(self):
        profile = self.users['worker'].profile
        profile.employee_id = 'STAFF-17'
        profile.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            other = self.users['outsider'].profile
            other.employee_id = 'staff-17'
            other.save()

    def test_department_case_insensitive_uniqueness_is_enforced_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Department.objects.create(name='software', faculty='Another faculty')
