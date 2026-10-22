#!/usr/bin/env bash
# A consistent database + private-media backup during a short maintenance window.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if [[ "${1:-}" != --run ]]; then
  echo 'Usage: bash scripts/backup.sh --run BACKUP_DIRECTORY' >&2
  echo 'This briefly stops the selected Compose backend, exports DB and media, then restarts it.' >&2
  exit 2
fi
destination="${2:?Choose a new private backup directory}"
umask 077
mkdir -p "$(dirname -- "$destination")"
mkdir "$destination"
compose=(docker compose -p "${UNIFLOW_COMPOSE_PROJECT:-uniflow}" --env-file "${UNIFLOW_ENV_FILE:-.env}" -f compose.yaml)
if [[ -n "${UNIFLOW_COMPOSE_OVERRIDE:-}" ]]; then compose+=(-f "$UNIFLOW_COMPOSE_OVERRIDE"); fi
"${compose[@]}" config --quiet
backend_stopped=0
restart_backend() {
  if [[ "$backend_stopped" == 1 ]]; then "${compose[@]}" start backend >/dev/null; fi
}
trap restart_backend EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"${compose[@]}" stop backend
backend_stopped=1
"${compose[@]}" exec -T database sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$destination/postgres.dump"
# A one-off container only reads the existing media volume; it does not run migrations.
"${compose[@]}" run --rm --no-deps --entrypoint sh backend -c 'exec tar -C "$DJANGO_MEDIA_ROOT" -czf - .' > "$destination/media.tar.gz"
python3 - "$destination" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
directory=Path(sys.argv[1])
files={}
for name in ['postgres.dump','media.tar.gz']:
 path=directory/name
 with path.open('rb') as stream:
  digest=hashlib.file_digest(stream,'sha256').hexdigest()
 files[name]={'sha256':digest,'bytes':path.stat().st_size}
manifest={'created_at':datetime.now(timezone.utc).isoformat(),'files':files,
 'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain']))}
(directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
PY
echo 'Backup complete; verify manifest, encrypt the backup, and test restoration on an isolated project.'
