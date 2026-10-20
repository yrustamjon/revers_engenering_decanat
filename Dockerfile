# syntax=docker/dockerfile:1
FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_STATIC_ROOT=/var/lib/uniflow/static \
    DJANGO_MEDIA_ROOT=/var/lib/uniflow/media
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 uniflow \
    && useradd --uid 10001 --gid 10001 --no-create-home uniflow \
    && mkdir -p /var/lib/uniflow/static /var/lib/uniflow/media \
    && chown -R uniflow:uniflow /var/lib/uniflow
COPY --chown=uniflow:uniflow backend/ ./
COPY --chown=uniflow:uniflow deploy/entrypoint.sh deploy/healthcheck.py /app/deploy/
USER uniflow
EXPOSE 8000
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]

FROM nginx:1.28-alpine AS frontend
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /build/frontend/dist/ /usr/share/nginx/html/
EXPOSE 8080
