from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        cache.set('readiness', 'ok', timeout=30)
        if cache.get('readiness') != 'ok':
            raise RuntimeError('Cache unavailable')
    except Exception:
        # Return no infrastructure, database or credential details publicly.
        return JsonResponse({'ready': False}, status=503)
    return JsonResponse({'ready': True})
