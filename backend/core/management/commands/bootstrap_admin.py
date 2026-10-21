"""Optional first administrator for hosts without an interactive shell."""
import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction


class Command(BaseCommand):
    help = 'Create the first administrator from UNIFLOW_ADMIN_* environment variables.'

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.environ.get('UNIFLOW_ADMIN_USERNAME', '')
        password = os.environ.get('UNIFLOW_ADMIN_PASSWORD', '')
        email = os.environ.get('UNIFLOW_ADMIN_EMAIL', '')
        if not username and not password:
            self.stdout.write('Administrator bootstrap skipped.')
            return
        if not username or not password:
            raise CommandError('Set both UNIFLOW_ADMIN_USERNAME and UNIFLOW_ADMIN_PASSWORD.')
        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing:
            if not existing.is_superuser or not existing.is_active:
                raise CommandError('Bootstrap name belongs to a non-administrator or inactive account.')
            self.stdout.write('Administrator already exists; password unchanged.')
            return
        user = User(username=username, email=email)
        try:
            User._meta.get_field('username').clean(username, user)
            if email:
                validate_email(email)
            validate_password(password, user=user)
        except ValidationError:
            raise CommandError('Invalid administrator username, email or password. Use a strong unique password.') from None
        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write('Initial administrator created.')
