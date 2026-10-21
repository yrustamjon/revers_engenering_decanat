#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py bootstrap_admin
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --threads 2 --timeout 90 --access-logfile - --error-logfile -
