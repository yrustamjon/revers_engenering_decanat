"""Service integration check, enabled when DJANGO_REDIS_URL is configured."""
import os
import subprocess
import sys
import uuid
from unittest import skipUnless

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase


@skipUnless(os.environ.get('DJANGO_REDIS_URL'), 'Requires a Redis service')
class SharedCacheTests(SimpleTestCase):
    def test_counter_is_shared_across_independent_workers(self):
        key = 'worker-check:' + uuid.uuid4().hex
        self.addCleanup(cache.delete, key)
        cache.add(key, 1, timeout=30)
        program = (
            'import django, sys; django.setup(); '
            'from django.core.cache import cache; '
            'assert cache.incr(sys.argv[1]) == 2'
        )
        subprocess.run(
            [sys.executable, '-c', program, key],
            cwd=settings.BASE_DIR,
            env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings'},
            check=True, timeout=15, capture_output=True,
        )
        self.assertEqual(cache.get(key), 2)
