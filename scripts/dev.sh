#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  echo "Install dependencies first: bash scripts/setup.sh" >&2
  exit 1
fi
.venv/bin/python - <<'PY'
import socket
for port in (8000, 5173):
    with socket.socket() as listener:
        try:
            listener.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'Port {port} is already in use. Stop its service before starting UniFlow.')
PY
service_pids=()
cleanup() {
  trap - EXIT INT TERM
  for service_pid in "${service_pids[@]}"; do
    kill "$service_pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'cleanup; exit 0' INT TERM
.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload &
service_pids+=("$!")
node frontend/node_modules/vite/bin/vite.js frontend --host 127.0.0.1 --port 5173 --strictPort &
service_pids+=("$!")
echo "UniFlow frontend: port 5173. Backend: port 8000. Ctrl+C stops both."
# macOS ships Bash 3.2, which has no wait -n.
while true; do
  for service_pid in "${service_pids[@]}"; do
    if ! kill -0 "$service_pid" 2>/dev/null; then
      wait "$service_pid"
      exit 0
    fi
  done
  sleep 1
done
