from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Activity, Department, Report, ReportTemplate


class AdministrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user('institution_admin', first_name='Madina', last_name='Usmonova', password='Compass!Larch92River')
        self.admin.profile.role = 'administrator'
        self.admin.profile.save()
        self.employee = User.objects.create_user('institution_employee', first_name='Azizbek', password='Compass!Larch92River')
        self.department = Department.objects.create(name='Software department', faculty='Engineering faculty', head_name='Department Head')
        self.employee.profile.department = self.department.name
        self.employee.profile.faculty = self.department.faculty
        self.employee.profile.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def payload(self, **overrides):
        return {'username': 'new_employee', 'full_name': 'Haqiqiy Xodim', 'email': 'new@example.com', 'role': 'employee', 'department': self.department.name, 'position': 'Lecturer', 'employee_id': 'EMP-002', 'password': 'Compass!Larch92River', **overrides}

    def test_non_administrators_denied_all_administration_routes(self):
        self.client.force_authenticate(user=self.employee)
        for route in ['users', 'departments', 'templates']:
            self.assertEqual(self.client.get(f'/api/admin/{route}/').status_code, 403)
            self.assertEqual(self.client.post(f'/api/admin/{route}/', {}, format='json').status_code, 403)

    def test_create_real_user_password_is_hashed_and_never_returned(self):
        response = self.client.post('/api/admin/users/', self.payload(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('password', response.data)
        self.assertFalse(response.data['is_demo'])
        self.assertEqual(response.data['faculty'], self.department.faculty)
        user = get_user_model().objects.get(pk=response.data['id'])
        self.assertTrue(user.check_password('Compass!Larch92River'))
        self.assertNotEqual(user.password, 'Compass!Larch92River')
        listing = self.client.get('/api/admin/users/')
        self.assertIsInstance(listing.data, list)
        self.assertTrue(all('password' not in item for item in listing.data))

    def test_create_user_requires_valid_password_and_known_department(self):
        self.assertEqual(self.client.post('/api/admin/users/', self.payload(password='123'), format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/admin/users/', self.payload(department='Invented'), format='json').status_code, 400)
        missing = self.payload()
        missing.pop('password')
        self.assertEqual(self.client.post('/api/admin/users/', missing, format='json').status_code, 400)

    def test_accounts_are_deactivated_not_deleted(self):
        response = self.client.patch(f'/api/admin/users/{self.employee.pk}/', {'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['is_active'])
        self.assertEqual(self.client.delete(f'/api/admin/users/{self.employee.pk}/').status_code, 405)
        auth = APIClient()
        self.assertEqual(auth.post('/api/auth/login/', {'username': 'institution_employee', 'password': 'Compass!Larch92River'}, format='json').status_code, 401)

    def test_last_active_administrator_cannot_be_demoted_or_deactivated(self):
        self.assertEqual(self.client.patch(f'/api/admin/users/{self.admin.pk}/', {'role': 'employee'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/admin/users/{self.admin.pk}/', {'is_active': False}, format='json').status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_promotion_and_demotion_when_another_admin_exists(self):
        response = self.client.patch(f'/api/admin/users/{self.employee.pk}/', {'role': 'administrator'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_staff)
        response = self.client.patch(f'/api/admin/users/{self.employee.pk}/', {'role': 'employee'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_staff)

    def test_staff_and_superuser_map_to_administrator(self):
        staff = get_user_model().objects.create_user('staff_admin', is_staff=True)
        self.client.force_authenticate(user=staff)
        self.assertEqual(self.client.get('/api/workspace/').data['user']['role'], 'administrator')
        response = self.client.patch(f'/api/admin/users/{staff.pk}/', {'position': 'Manager'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        staff.refresh_from_db()
        self.assertTrue(staff.is_staff)
        self.assertEqual(staff.profile.role, 'administrator')

    def test_department_rename_updates_profile_assignments(self):
        response = self.client.patch(f'/api/admin/departments/{self.department.pk}/', {'name': 'Software engineering', 'faculty': 'New faculty'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.profile.refresh_from_db()
        self.assertEqual(self.employee.profile.department, 'Software engineering')
        self.assertEqual(self.employee.profile.faculty, 'New faculty')
        duplicate = self.client.post('/api/admin/departments/', {'name': 'software engineering', 'faculty': 'Other'}, format='json')
        self.assertEqual(duplicate.status_code, 400)

    def test_template_edit_requires_version_and_report_snapshot_is_immutable(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post('/api/reports/', {'title': 'Report', 'type': 'scientific', 'period': '2026', 'template_id': 'scientific-v1'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        report = response.data
        self.assertEqual(report['template_version'], '1.0')
        old_title = report['template_snapshot']['title']
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch('/api/admin/templates/scientific-v1/', {'title': 'Updated title'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.patch('/api/admin/templates/scientific-v1/', {'title': 'Updated title', 'version': '2.0'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['version'], '2.0')
        self.client.force_authenticate(user=self.employee)
        original = self.client.get(f'/api/reports/{report["id"]}/').data
        self.assertEqual(original['template_version'], '1.0')
        self.assertEqual(original['template_snapshot']['title'], old_title)
        fresh = self.client.post('/api/reports/', {'title': 'New report', 'type': 'scientific', 'period': '2026'}, format='json')
        self.assertEqual(fresh.data['template_version'], '2.0')

    def test_custom_template_create_and_deactivate(self):
        response = self.client.post('/api/admin/templates/', {'id': 'custom-annual', 'title': 'Custom annual', 'description': 'A custom template', 'type': 'annual', 'version': '1.0', 'fields': ['Natijalar', 'Dalillar'], 'icon': 'BookOpen', 'is_active': True}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['id'], 'custom-annual')
        self.assertEqual(self.client.patch('/api/admin/templates/custom-annual/', {'id': 'renamed'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch('/api/admin/templates/custom-annual/', {'is_active': False}, format='json').status_code, 200)
        self.client.force_authenticate(user=self.employee)
        self.assertNotIn('custom-annual', [item['id'] for item in self.client.get('/api/workspace/').data['templates']])
        self.assertEqual(self.client.post('/api/reports/', {'title': 'Report', 'type': 'annual', 'period': '2026', 'template_id': 'custom-annual'}, format='json').status_code, 400)

    def test_administrator_can_review_other_department_but_not_own(self):
        report = Report.objects.create(owner=self.employee, title='Report', type='annual', period='2026', status='submitted')
        self.assertEqual(self.client.post(f'/api/reports/{report.pk}/review/', {'decision': 'approved'}, format='json').status_code, 200)
        own = Report.objects.create(owner=self.admin, title='Own', type='annual', period='2026', status='submitted')
        self.assertEqual(self.client.post(f'/api/reports/{own.pk}/review/', {'decision': 'approved'}, format='json').status_code, 404)

    def test_change_password_checks_current_validates_new_and_preserves_session(self):
        auth = APIClient()
        self.assertTrue(auth.login(username='institution_employee', password='Compass!Larch92River'))
        self.assertEqual(auth.post('/api/auth/password/', {'current_password': 'wrong', 'new_password': 'Another!Birch39Forest'}, format='json').status_code, 400)
        self.assertEqual(auth.post('/api/auth/password/', {'current_password': 'Compass!Larch92River', 'new_password': '123'}, format='json').status_code, 400)
        self.assertEqual(auth.post('/api/auth/password/', {'current_password': 'Compass!Larch92River', 'new_password': 'Another!Birch39Forest'}, format='json').status_code, 204)
        self.assertEqual(auth.get('/api/auth/session/').status_code, 200)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password('Another!Birch39Forest'))
        self.assertFalse(self.employee.check_password('Compass!Larch92River'))

    def test_password_change_requires_authentication(self):
        anonymous = APIClient()
        self.assertEqual(anonymous.post('/api/auth/password/', {'current_password': 'x', 'new_password': 'Another!Birch39Forest'}, format='json').status_code, 403)

    def test_employee_id_is_unique_and_reviewer_requires_department(self):
        self.employee.profile.employee_id = 'EMP-002'
        self.employee.profile.save()
        self.assertEqual(self.client.post('/api/admin/users/', self.payload(), format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/admin/users/', self.payload(employee_id='EMP-003', role='reviewer', department=''), format='json').status_code, 400)

    def test_custom_schema_required_values_validate_on_submit_against_snapshot(self):
        schema = [{'key': 'journal', 'label': 'Jurnal nomi', 'type': 'text', 'required': True}, {'key': 'pages', 'label': 'Sahifalar', 'type': 'number', 'required': True}, {'key': 'published', 'label': 'Nashr sanasi', 'type': 'date', 'required': True}, {'key': 'source', 'label': 'Manba', 'type': 'url', 'required': True}]
        response = self.client.post('/api/admin/templates/', {'id': 'custom-schema', 'title': 'Custom scientific', 'description': 'Structured fields', 'type': 'scientific', 'version': '1.0', 'fields': ['Ilmiy faoliyat'], 'form_schema': schema}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.client.force_authenticate(user=self.employee)
        activity = Activity.objects.create(owner=self.employee, title='Article', category='article', date='2026-10-01', link='https://example.com/article')
        response = self.client.post('/api/reports/', {'title': 'Report', 'type': 'scientific', 'period': '2026', 'template_id': 'custom-schema', 'activity_ids': [activity.pk]}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        report_id = response.data['id']
        self.assertEqual(response.data['template_snapshot']['form_schema'], schema)
        response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('journal', response.data['extra_data'])
        bad_values = {'journal': 'Journal', 'pages': True, 'published': 'bad-date', 'source': 'javascript:alert(1)', 'unknown': 'Invalid'}
        self.assertEqual(self.client.patch(f'/api/reports/{report_id}/', {'extra_data': bad_values}, format='json').status_code, 200)
        response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        for key in ['pages', 'published', 'source', 'unknown']:
            self.assertIn(key, response.data['extra_data'])
        values = {'journal': 'Real Journal', 'pages': 12, 'published': '2026-10-01', 'source': 'https://example.com/publication'}
        self.assertEqual(self.client.patch(f'/api/reports/{report_id}/', {'extra_data': values}, format='json').status_code, 200)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.patch('/api/admin/templates/custom-schema/', {'version': '2.0', 'form_schema': schema + [{'key': 'new_field', 'label': 'New', 'type': 'text', 'required': True}]}, format='json').status_code, 200)
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['template_version'], '1.0')
        self.assertEqual(response.data['extra_data'], values)
        self.assertEqual(response.data['template_snapshot']['form_schema'], schema)
        self.assertEqual(self.client.patch(f'/api/reports/{report_id}/', {'extra_data': {'journal': 'Changed'}}, format='json').status_code, 400)

    def test_schema_rejects_duplicate_unsafe_or_unknown_field_types(self):
        base = {'id': 'bad-schema', 'title': 'Invalid', 'description': 'Invalid schema', 'type': 'annual', 'version': '1.0', 'fields': ['Result']}
        for schema in [
            [{'key': '__proto__', 'label': 'Bad', 'type': 'text', 'required': False}],
            [{'key': 'field', 'label': 'Bad', 'type': 'html', 'required': False}],
            [{'key': 'same', 'label': 'First', 'type': 'text'}, {'key': 'same', 'label': 'Second', 'type': 'text'}],
        ]:
            response = self.client.post('/api/admin/templates/', {**base, 'form_schema': schema}, format='json')
            self.assertEqual(response.status_code, 400, response.data)

    def test_login_lock_is_scoped_to_username_and_ip_with_broad_ip_ceiling(self):
        cache.clear()
        self.addCleanup(cache.clear)
        anonymous = APIClient()
        for _ in range(10):
            self.assertEqual(anonymous.post('/api/auth/login/', {'username': 'locked_user', 'password': 'wrong'}, format='json').status_code, 401)
        self.assertEqual(anonymous.post('/api/auth/login/', {'username': 'locked_user', 'password': 'wrong'}, format='json').status_code, 429)
        self.assertEqual(anonymous.post('/api/auth/login/', {'username': 'institution_employee', 'password': 'Compass!Larch92River'}, format='json').status_code, 200)
        self.assertEqual(anonymous.post('/api/auth/login/', {'username': 'locked_user', 'password': 'wrong'}, format='json', REMOTE_ADDR='127.0.0.2').status_code, 401)
