import shutil
import tempfile
from io import StringIO
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Activity, Attachment, History, Notification, Report, WorkItem


class WorkflowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.mkdtemp(prefix='uniflow-tests-')
        cls.media_override = override_settings(MEDIA_ROOT=cls.media)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        self.employee = User.objects.create_user('worker', first_name='Azizbek', last_name='Karimov', password='test-secret')
        self.other = User.objects.create_user('other', first_name='Other')
        self.reviewer = User.objects.create_user('reviewer', first_name='Dilshod')
        self.outsider = User.objects.create_user('outsider')
        for user, department, role in [(self.employee, 'Software', 'employee'), (self.other, 'Software', 'employee'), (self.reviewer, 'Software', 'reviewer'), (self.outsider, 'Other department', 'reviewer')]:
            user.profile.department = department
            user.profile.role = role
            user.profile.save()
        self.activity = Activity.objects.create(owner=self.employee, title='Ilmiy maqola', category='article', date='2026-10-01', link='https://example.com/article')
        self.report = Report.objects.create(owner=self.employee, title='Ilmiy hisobot', type='scientific', period='2026')
        self.report.activities.add(self.activity)
        self.client = APIClient()
        self.client.force_authenticate(user=self.employee)

    def submit(self):
        response = self.client.post(f'/api/reports/{self.report.pk}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def test_anonymous_access_denied_and_csrf_cookie_set(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.get('/api/auth/session/')
        self.assertEqual(response.status_code, 401)
        self.assertIn('csrftoken', response.cookies)
        self.assertEqual(client.get('/api/workspace/').status_code, 403)
        self.assertEqual(client.post('/api/auth/login/', {'username': 'worker', 'password': 'test-secret'}, format='json').status_code, 403)
        token = client.cookies['csrftoken'].value
        response = client.post('/api/auth/login/', {'username': 'worker', 'password': 'test-secret'}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get('/api/workspace/').status_code, 200)
        self.assertEqual(client.post('/api/reports/', {'title': 'No token'}, format='json').status_code, 403)

    def test_employee_cannot_read_or_modify_other_records(self):
        private = Report.objects.create(owner=self.other, title='Private', type='annual', period='2026')
        private_activity = Activity.objects.create(owner=self.other, title='Private activity', category='project', date='2026-10-01')
        workspace = self.client.get('/api/workspace/').data
        self.assertEqual([r['id'] for r in workspace['reports']], [self.report.pk])
        self.assertEqual(workspace['reports'][0]['owner_id'], self.employee.pk)
        self.assertEqual(workspace['activities'][0]['owner_id'], self.employee.pk)
        self.assertNotIn(private_activity.pk, [a['id'] for a in workspace['activities']])
        self.assertEqual(self.client.get(f'/api/reports/{private.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/activities/{private_activity.pk}/', {'title': 'Hack'}, format='json').status_code, 404)

    def test_submit_return_resubmit_approve_workflow_and_history(self):
        self.submit()
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(f'/api/reports/{self.report.pk}/review/', {'decision': 'returned', 'comment': 'Jurnal nomini aniqlashtiring.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'returned')
        self.client.force_authenticate(user=self.employee)
        self.assertEqual(self.client.patch(f'/api/activities/{self.activity.pk}/', {'description': 'Tuzatildi'}, format='json').status_code, 200)
        self.submit()
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(f'/api/reports/{self.report.pk}/review/', {'decision': 'approved', 'comment': 'Qabul qilindi.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'approved')
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.status, 'verified')
        self.assertEqual(list(self.report.history.values_list('action', flat=True)), ['submitted', 'returned', 'submitted', 'approved'])
        self.assertEqual(Notification.objects.filter(owner=self.employee).count(), 2)

    def test_submitted_report_and_evidence_are_immutable(self):
        self.submit()
        self.assertEqual(self.client.patch(f'/api/reports/{self.report.pk}/', {'title': 'Changed'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/reports/{self.report.pk}/').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/activities/{self.activity.pk}/', {'title': 'Changed'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/activities/{self.activity.pk}/').status_code, 400)

    def test_approved_report_remains_immutable(self):
        self.report.status = 'approved'
        self.report.save()
        self.assertEqual(self.client.patch(f'/api/reports/{self.report.pk}/', {'period': '2025'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/activities/{self.activity.pk}/').status_code, 400)

    def test_missing_evidence_prevents_submission(self):
        self.activity.link = ''
        self.activity.save()
        response = self.client.post(f'/api/reports/{self.report.pk}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('activity_ids', response.data)
        self.report.activities.clear()
        self.assertEqual(self.client.post(f'/api/reports/{self.report.pk}/submit/', {}, format='json').status_code, 400)

    def test_only_reviewer_can_decide_and_not_own_report(self):
        self.submit()
        self.assertEqual(self.client.post(f'/api/reports/{self.report.pk}/review/', {'decision': 'approved'}, format='json').status_code, 403)
        own = Report.objects.create(owner=self.reviewer, title='Own', type='annual', period='2026', status='submitted')
        self.client.force_authenticate(user=self.reviewer)
        self.assertEqual(self.client.post(f'/api/reports/{own.pk}/review/', {'decision': 'approved'}, format='json').status_code, 404)

    def test_reviewer_is_scoped_to_department_and_cannot_edit(self):
        self.submit()
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(self.client.get(f'/api/reports/{self.report.pk}/').status_code, 404)
        self.assertEqual(self.client.get('/api/workspace/').data['reports'], [])
        self.client.force_authenticate(user=self.reviewer)
        self.assertEqual(self.client.get(f'/api/reports/{self.report.pk}/').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/reports/{self.report.pk}/', {'title': 'Not allowed'}, format='json').status_code, 403)

    def test_return_requires_comment_and_invalid_transition_rejected(self):
        self.submit()
        self.client.force_authenticate(user=self.reviewer)
        self.assertEqual(self.client.post(f'/api/reports/{self.report.pk}/review/', {'decision': 'returned', 'comment': ''}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/reports/{self.report.pk}/review/', {'decision': 'invalid'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/reports/{self.report.pk}/review/', {'decision': 'approved'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/reports/{self.report.pk}/review/', {'decision': 'returned', 'comment': 'too late'}, format='json').status_code, 400)

    def test_cannot_attach_other_users_activity(self):
        other_activity = Activity.objects.create(owner=self.other, title='Other', category='article', date='2026-10-01')
        response = self.client.post('/api/reports/', {'title': 'Attempt', 'type': 'annual', 'period': '2026', 'activity_ids': [other_activity.pk]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('activity_ids', response.data)

    def test_profile_edit_does_not_change_organization_or_role(self):
        response = self.client.patch('/api/profile/', {'full_name': 'Yangi Ism', 'email': 'new@example.com', 'phone': '+998901112233', 'bio': 'Yangi tavsif', 'department': 'Other department', 'role': 'reviewer'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['full_name'], 'Yangi Ism')
        self.employee.refresh_from_db()
        self.employee.profile.refresh_from_db()
        self.assertEqual(self.employee.email, 'new@example.com')
        self.assertEqual(self.employee.profile.role, 'employee')
        self.assertEqual(self.employee.profile.department, 'Software')

    def test_authenticated_upload_download_and_owner_access(self):
        response = self.client.post('/api/attachments/', {'file': SimpleUploadedFile('evidence.txt', b'Proof of work')}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        attachment_id = response.data['id']
        url = response.data['url']
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post('/api/activities/', {'title': 'Attempt', 'category': 'article', 'date': '2026-10-01', 'attachment_id': attachment_id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(user=self.employee)
        self.client.patch(f'/api/activities/{self.activity.pk}/', {'attachment_id': attachment_id}, format='json')
        self.submit()
        self.client.force_authenticate(user=self.reviewer)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_upload_rejects_active_content(self):
        response = self.client.post('/api/attachments/', {'file': SimpleUploadedFile('evil.html', b'<script>alert(1)</script>')}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_work_plan_validation_and_owner_isolation(self):
        response = self.client.post('/api/work-items/', {'title': 'Reja', 'category': 'article', 'target': 2, 'completed': 3, 'due_date': '2026-12-01'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/work-items/', {'title': 'Reja', 'category': 'article', 'target': 2, 'completed': 1, 'due_date': '2026-12-01'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.patch(f'/api/work-items/{response.data["id"]}/', {'completed': 2}, format='json').status_code, 404)

    def test_user_cannot_self_verify_activity_or_approve_report(self):
        response = self.client.patch(f'/api/activities/{self.activity.pk}/', {'status': 'verified'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'draft')
        response = self.client.patch(f'/api/reports/{self.report.pk}/', {'status': 'approved'}, format='json')
        self.assertEqual(response.data['status'], 'draft')

    @override_settings(DEBUG=True)
    def test_seed_is_idempotent_and_demo_auth_is_development_only(self):
        call_command('seed_demo', stdout=StringIO())
        employee = get_user_model().objects.get(username='demo_employee')
        count = employee.activities.count()
        activity = employee.activities.first()
        activity.description = 'User edit must survive reseeding'
        activity.save()
        call_command('seed_demo', stdout=StringIO())
        activity.refresh_from_db()
        self.assertEqual(employee.activities.count(), count)
        self.assertEqual(activity.description, 'User edit must survive reseeding')
        client = APIClient()
        self.assertEqual(client.post('/api/auth/demo/', {'role': 'employee'}, format='json').status_code, 200)
        with override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False):
            self.assertEqual(client.post('/api/auth/demo/', {'role': 'reviewer'}, format='json').status_code, 404)
