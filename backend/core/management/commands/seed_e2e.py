"""Private, password-authenticated fixtures for isolated browser testing only."""
import json
import os
import secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Activity, Department


class Command(BaseCommand):
    help = 'Prepare password-based browser test accounts in an explicitly enabled test environment.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or os.environ.get('UNIFLOW_E2E') != '1':
            raise CommandError('Browser fixtures require DEBUG=1 and UNIFLOW_E2E=1; never run against production.')
        directory = settings.BASE_DIR.parent / '.local' / 'e2e'
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        path = directory / 'accounts.json'
        credentials = json.loads(path.read_text()) if path.exists() else {}
        department, _ = Department.objects.get_or_create(name='E2E Software', defaults={'faculty':'E2E Engineering'})
        for role in ['employee', 'reviewer', 'administrator']:
            record = credentials.setdefault(role, {'username':'e2e_local_'+role, 'password':secrets.token_urlsafe(24)})
            user, _ = get_user_model().objects.get_or_create(username=record['username'])
            user.first_name, user.last_name = 'E2E', role.title()
            user.email = role+'@example.com'
            user.is_active, user.is_staff = True, role == 'administrator'
            user.set_password(record['password'])
            user.save()
            user.profile.role = role
            user.profile.department, user.profile.faculty = department.name, department.faculty
            user.profile.position = 'E2E Staff'
            user.profile.save()
            if role == 'employee':
                for index, category in enumerate(['article','teaching','certificate','project','conference','article','certificate','teaching']):
                    Activity.objects.get_or_create(owner=user, title=f'E2E Initial Activity {index+1}', defaults={'category':category,'date':timezone.localdate(),'description':'Isolated browser test fixture','link':'https://example.com/evidence'})
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(credentials, output)
        self.stdout.write('Password-based browser fixtures prepared; credentials remain in ignored private state.')
