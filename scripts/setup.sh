#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --cache-dir "$repo_root/.local/pip-cache" -r backend/requirements.txt
npm ci --prefix frontend --cache "$repo_root/.local/npm-cache" --no-audit --no-fund
.venv/bin/python backend/manage.py migrate --noinput
if [[ "${1:-}" == "--demo" ]]; then
  .venv/bin/python backend/manage.py seed_demo
fi
npm run build --prefix frontend
.venv/bin/python backend/manage.py check
echo "UniFlow setup complete. Start development with bash scripts/dev.sh."
