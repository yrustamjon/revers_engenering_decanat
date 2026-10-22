import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY is required when DJANGO_DEBUG=0.')
    SECRET_KEY = 'uniflow-local-development-only-not-for-production'
RENDER_HOST = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '') if os.environ.get('RENDER') == 'true' else ''
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', RENDER_HOST or 'localhost,127.0.0.1,[::1]').split(',') if h.strip()]
if not DEBUG and not os.environ.get('DJANGO_ALLOWED_HOSTS') and not RENDER_HOST:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS is required in production.')

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'core.apps.CoreConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.security.PrivateResponseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
if os.environ.get('POSTGRES_HOST'):
    required_database_values = ['POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
    missing_database_values = [name for name in required_database_values if not os.environ.get(name)]
    if missing_database_values:
        raise ImproperlyConfigured('Missing database configuration: ' + ', '.join(missing_database_values))
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': os.environ['POSTGRES_HOST'],
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'NAME': os.environ['POSTGRES_DB'],
        'USER': os.environ['POSTGRES_USER'],
        'PASSWORD': os.environ['POSTGRES_PASSWORD'],
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer')},
    }}
else:
    if not DEBUG:
        raise ImproperlyConfigured('POSTGRES_HOST and database credentials are required in production.')
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3', 'OPTIONS': {'timeout': 20}}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = Path(os.environ.get('DJANGO_STATIC_ROOT', BASE_DIR / 'staticfiles'))
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', BASE_DIR / 'media'))
UPLOADS_ENABLED = os.environ.get('DJANGO_UPLOADS_ENABLED', '1') == '1'
FRONTEND_ROOT = os.environ.get('DJANGO_FRONTEND_ROOT', '')
if FRONTEND_ROOT:
    from .frontend import static_headers
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    WHITENOISE_ROOT = FRONTEND_ROOT
    WHITENOISE_INDEX_FILE = True
    WHITENOISE_ADD_HEADERS_FUNCTION = static_headers
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
REDIS_URL = os.environ.get('DJANGO_REDIS_URL', '')
if REDIS_URL:
    CACHES = {'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'KEY_PREFIX': 'uniflow',
        'OPTIONS': {'socket_connect_timeout': 3, 'socket_timeout': 3},
    }}
elif not DEBUG:
    raise ImproperlyConfigured('DJANGO_REDIS_URL is required for shared production rate limits.')
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_THROTTLE_CLASSES': ['core.security.TrustedAnonThrottle', 'core.security.TrustedUserThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '60/min', 'user': '600/min'},
}
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', ('https://' + RENDER_HOST) if RENDER_HOST else ('http://localhost:5173,http://127.0.0.1:5173' if DEBUG else '')).split(',') if v.strip()]
if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured('DJANGO_CSRF_TRUSTED_ORIGINS is required in production.')
# Only enable behind the dedicated, trusted proxy described in docs/DEPLOYMENT.md.
# The backend port must never be exposed directly to clients when this is enabled.
if os.environ.get('DJANGO_TRUST_PROXY') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
TRUSTED_PROXY_CIDRS = [value.strip() for value in os.environ.get('DJANGO_TRUSTED_PROXY_CIDRS', '').split(',') if value.strip()]
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 22 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r'^healthz$']
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
