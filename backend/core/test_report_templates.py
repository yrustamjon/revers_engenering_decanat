from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Activity, History, Report, ReportTemplate


class ReportTemplateSelectionTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user('template_employee')
        self.client = APIClient()
        self.client.force_authenticate(self.employee)
        self.template = ReportTemplate.objects.get(pk='scientific-v1')
        self.template.form_schema = [
            {'key': 'journal', 'label': 'Jurnal nomi', 'type': 'text', 'required': True},
        ]
        self.template.save()
        self.activity = Activity.objects.create(
            owner=self.employee, title='Article', category='article',
            date='2026-10-01', link='https://example.com/article',
        )
        self.payload = {
            'title': 'Scientific report', 'type': 'scientific', 'period': '2026',
            'activity_ids': [self.activity.pk],
        }

    def test_missing_active_template_cannot_create_schemaless_report(self):
        ReportTemplate.objects.filter(type='scientific').update(is_active=False)

        response = self.client.post('/api/reports/', self.payload, format='json')

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('template_id', response.data)
        self.assertFalse(Report.objects.filter(owner=self.employee).exists())
        self.assertFalse(History.objects.filter(actor=self.employee).exists())

    def test_implicit_template_preserves_required_fields_on_submit(self):
        response = self.client.post('/api/reports/', self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['template_snapshot']['id'], self.template.pk)
        self.assertEqual(response.data['template_snapshot']['form_schema'], self.template.form_schema)
        report_id = response.data['id']

        response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('journal', response.data['extra_data'])

    def test_deactivating_template_keeps_existing_draft_snapshot_usable(self):
        response = self.client.post('/api/reports/', self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        report_id = response.data['id']
        snapshot = response.data['template_snapshot']
        ReportTemplate.objects.filter(pk=self.template.pk).update(is_active=False)

        response = self.client.patch(
            f'/api/reports/{report_id}/', {'extra_data': {'journal': 'Real journal'}}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['template_snapshot'], snapshot)
        response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['template_snapshot'], snapshot)

    def test_legacy_report_without_template_cannot_bypass_submission_validation(self):
        for missing_fields in [
            {'template_snapshot': {}, 'template_version': ''},
            {'template_snapshot': {}},
            {'template_version': ''},
        ]:
            with self.subTest(missing_fields=missing_fields):
                response = self.client.post('/api/reports/', self.payload, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                report_id = response.data['id']
                Report.objects.filter(pk=report_id).update(**missing_fields)

                response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')

                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('template_id', response.data)
                report = Report.objects.get(pk=report_id)
                self.assertEqual(report.status, 'draft')
                self.assertIsNone(report.submitted_at)
                self.assertFalse(report.history.filter(action='submitted').exists())

    def test_date_fields_require_canonical_calendar_date(self):
        self.template.form_schema = [
            {'key': 'published', 'label': 'Nashr sanasi', 'type': 'date', 'required': True},
        ]
        self.template.save()
        response = self.client.post('/api/reports/', self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        report_id = response.data['id']

        for value in ['20261001', '2026-W40-4', '2026-02-30']:
            with self.subTest(value=value):
                response = self.client.patch(
                    f'/api/reports/{report_id}/', {'extra_data': {'published': value}}, format='json',
                )
                self.assertEqual(response.status_code, 200, response.data)
                response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('published', response.data['extra_data'])

        response = self.client.patch(
            f'/api/reports/{report_id}/', {'extra_data': {'published': '2026-10-01'}}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.post(f'/api/reports/{report_id}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
