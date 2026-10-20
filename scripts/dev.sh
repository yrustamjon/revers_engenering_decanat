#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  echo "Install dependencies first: bash scripts/setup.sh --demo" >&2
  exit 1
fi
service_pids=()
cleanup() {
  trap - EXIT INT TERM
  for service_pid in "${service_pids[@]}"; do
    kill "$service_pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM
.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload &
service_pids+=("$!")
npm run dev --prefix frontend &
service_pids+=("$!")
echo "UniFlow frontend: port 5173. Backend: port 8000. Ctrl+C stops both."
wait -n "${service_pids[@]}"
