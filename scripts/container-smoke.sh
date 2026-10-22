#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
image="${1:?Usage: bash scripts/container-smoke.sh IMAGE}"
smoke_id="uniflow-check-$$"
mkdir -p .local/container-check
smoke_dir="$(mktemp -d "$repo_root/.local/container-check/run.XXXXXX")"
cleanup() {
  trap - EXIT INT TERM
  docker rm -f "$smoke_id-web" "$smoke_id-db" "$smoke_id-cache" >/dev/null 2>&1 || true
  docker network rm "$smoke_id" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 - "$smoke_dir" <<'PY'
import os, secrets, sys
from pathlib import Path
directory = Path(sys.argv[1])
password = secrets.token_urlsafe(32)
values = {
 'POSTGRES_DB':'uniflow_check', 'POSTGRES_USER':'uniflow_check', 'POSTGRES_PASSWORD':password,
 'POSTGRES_HOST':'database', 'POSTGRES_SSLMODE':'disable',
 'DJANGO_REDIS_URL':'redis://cache:6379/0', 'DJANGO_SECRET_KEY':secrets.token_urlsafe(48),
 'RENDER':'true','RENDER_EXTERNAL_HOSTNAME':'uniflow-check.onrender.com', 'PORT':'10007',
 'UNIFLOW_ADMIN_USERNAME':'smoke_admin','UNIFLOW_ADMIN_PASSWORD':secrets.token_urlsafe(32),
}
path=directory/'runtime.env'
fd=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
with os.fdopen(fd,'w') as output:
 output.write(''.join(key+'='+value+'\n' for key,value in values.items()))
PY
docker network create "$smoke_id" >/dev/null
docker run -d --name "$smoke_id-db" --network "$smoke_id" --network-alias database \
  --env-file "$smoke_dir/runtime.env" postgres:17-alpine >/dev/null
docker run -d --name "$smoke_id-cache" --network "$smoke_id" --network-alias cache redis:8-alpine >/dev/null
ready=0
for attempt in $(seq 1 30); do
  if docker exec "$smoke_id-db" pg_isready -U uniflow_check -d uniflow_check >/dev/null 2>&1 && docker exec "$smoke_id-cache" redis-cli ping >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo 'Disposable database/cache did not become ready.' >&2; exit 1; }
docker run -d --name "$smoke_id-web" --network "$smoke_id" --env-file "$smoke_dir/runtime.env" "$image" >/dev/null
ready=0
for attempt in $(seq 1 45); do
  if docker exec "$smoke_id-web" python -c 'from urllib.request import Request,ProxyHandler,build_opener; assert build_opener(ProxyHandler({})).open(Request("http://127.0.0.1:10007/healthz",headers={"Host":"uniflow-check.onrender.com"}),timeout=2).status==200' >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then docker logs --tail 40 "$smoke_id-web"; exit 1; fi
docker exec -i "$smoke_id-web" python - < deploy/smoke.py
if [[ "${UNIFLOW_SMOKE_RUN_TESTS:-0}" == 1 ]]; then
  docker exec -e DJANGO_DEBUG=1 -e DJANGO_UPLOADS_ENABLED=1 "$smoke_id-web" python manage.py test core --verbosity 1
fi
echo 'Container smoke check passed; disposable containers are being removed.'
