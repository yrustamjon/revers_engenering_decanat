# syntax=docker/dockerfile:1
FROM node:25-alpine@sha256:bdf2cca6fe3dabd014ea60163eca3f0f7015fbd5c7ee1b0e9ccb4ced6eb02ef4 AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-alpine@sha256:92abd2ba1bdfb48b1e2ac224b582dd1558d0d4bb11c903b126b5bf9c448fd656 AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_STATIC_ROOT=/var/lib/uniflow/static \
    DJANGO_MEDIA_ROOT=/var/lib/uniflow/media
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir --upgrade pip==26.2.2 \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check \
    && python -m pip uninstall --yes pip setuptools wheel \
    && rm -rf /usr/local/lib/python3.12/ensurepip \
    && addgroup -S -g 10001 uniflow \
    && adduser -S -D -H -u 10001 -G uniflow uniflow \
    && mkdir -p /var/lib/uniflow/static /var/lib/uniflow/media \
    && chown -R uniflow:uniflow /var/lib/uniflow
COPY --chown=uniflow:uniflow backend/ ./
COPY --chown=uniflow:uniflow deploy/entrypoint.sh deploy/healthcheck.py /app/deploy/
USER uniflow
EXPOSE 8000
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]

FROM nginx:1.28-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236 AS frontend
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /build/frontend/dist/ /usr/share/nginx/html/
EXPOSE 8080
