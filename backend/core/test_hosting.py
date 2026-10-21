import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIClient

from .models import Attachment


class HostingTests(TestCase):
    def test_readiness_checks_services_without_authentication(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ready': True})

    def test_readiness_failure_exposes_no_infrastructure_details(self):
        with patch('config.health.cache.set', side_effect=RuntimeError('private connection details')):
            response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'ready': False})

    @override_settings(UPLOADS_ENABLED=False)
    def test_ephemeral_host_cannot_accept_files_that_would_be_lost(self):
        user = get_user_model().objects.create_user('hosting_worker')
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.post('/api/attachments/', {}, format='multipart').status_code, 503)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_react_and_api_share_origin_without_exposing_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'assets').mkdir()
            (root / 'static').mkdir()
            (root / 'index.html').write_text('<html>React build sentinel</html>')
            (root / 'assets' / 'app.js').write_text('window.example = true;')
            middleware = list(settings.MIDDLEWARE)
            middleware.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
            from config.frontend import static_headers
            with override_settings(MIDDLEWARE=middleware, WHITENOISE_ROOT=directory,
                                   WHITENOISE_INDEX_FILE=True, WHITENOISE_AUTOREFRESH=False,
                                   WHITENOISE_ADD_HEADERS_FUNCTION=static_headers,
                                   STATIC_ROOT=root / 'static'):
                client = Client()
                response = client.get('/')
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'React build sentinel', b''.join(response.streaming_content))
                self.assertEqual(response['Cache-Control'], 'no-store')
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(client.get('/assets/app.js').status_code, 200)
                self.assertEqual(client.get('/api/auth/session/').status_code, 401)
                self.assertEqual(client.get('/api/missing/').status_code, 404)
                self.assertEqual(client.get('/media/private.pdf').status_code, 404)


class BootstrapAdministratorTests(TestCase):
    def bootstrap(self, password='Compass!Larch92River'):
        with patch.dict(os.environ, {'UNIFLOW_ADMIN_USERNAME': 'initial_admin',
                                    'UNIFLOW_ADMIN_PASSWORD': password,
                                    'UNIFLOW_ADMIN_EMAIL': 'admin@example.com'}):
            call_command('bootstrap_admin', stdout=StringIO())

    def test_initial_admin_can_login_and_redeploy_does_not_reset_password(self):
        self.bootstrap()
        user = get_user_model().objects.get(username='initial_admin')
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertTrue(self.client.login(username='initial_admin', password='Compass!Larch92River'))
        self.bootstrap(password='Another!Birch39Forest')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Compass!Larch92River'))

    def test_bootstrap_cannot_promote_existing_employee(self):
        get_user_model().objects.create_user('initial_admin')
        with self.assertRaises(CommandError):
            self.bootstrap()
        self.assertFalse(get_user_model().objects.get(username='initial_admin').is_superuser)

    def test_weak_bootstrap_password_is_rejected(self):
        with self.assertRaises(CommandError):
            self.bootstrap(password='123')
        self.assertFalse(get_user_model().objects.filter(username='initial_admin').exists())
