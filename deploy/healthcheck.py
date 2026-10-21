"""Local Gunicorn readiness probe; no public health or credential output."""
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import psycopg
import redis

if os.environ.get('DJANGO_REDIS_URL'):
    try:
        redis.Redis.from_url(os.environ['DJANGO_REDIS_URL'], socket_connect_timeout=3, socket_timeout=3).ping()
    except redis.RedisError:
        sys.exit(1)

if os.environ.get('POSTGRES_HOST'):
    try:
        with psycopg.connect(
            host=os.environ['POSTGRES_HOST'],
            port=os.environ.get('POSTGRES_PORT', '5432'),
            dbname=os.environ['POSTGRES_DB'],
            user=os.environ['POSTGRES_USER'],
            password=os.environ['POSTGRES_PASSWORD'],
            sslmode=os.environ.get('POSTGRES_SSLMODE', 'prefer'),
            connect_timeout=3,
        ) as connection:
            connection.execute('SELECT 1').fetchone()
    except psycopg.Error:
        sys.exit(1)

host = os.environ['DJANGO_ALLOWED_HOSTS'].split(',')[0].strip()
request = Request('http://127.0.0.1:8000/api/auth/session/', headers={
    'Host': host,
    'X-Forwarded-Proto': 'https',
})
try:
    # This is the service in this container, never an external HTTP destination.
    with build_opener(ProxyHandler({})).open(request, timeout=4) as response:
        sys.exit(0 if response.status == 200 else 1)
except HTTPError as error:
    # An unauthenticated session is the expected health response.
    sys.exit(0 if error.code == 401 else 1)
except (URLError, OSError):
    sys.exit(1)
