#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
mkdir -p artifacts/security
security_python="${UNIFLOW_SECURITY_PYTHON:-$repo_root/.local/security-venv/bin/python}"
if [[ ! -x "$security_python" ]]; then
  echo 'Install tools first: python3 -m venv .local/security-venv; .local/security-venv/bin/pip install -r requirements-security.txt' >&2
  exit 1
fi
if [[ -n "${CODEX_PROXY_CERT:-}" ]]; then
  export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
fi
"$security_python" -m bandit -r backend \
  -x backend/core/tests.py,backend/core/test_administration.py,backend/core/test_hosting.py,backend/core/test_report_templates.py,backend/core/test_shared_cache.py,backend/core/test_mvp.py,backend/core/migrations \
  -ll -f json -o artifacts/security/bandit.json
"$security_python" -m pip_audit -r backend/requirements.txt --vulnerability-service pypi \
  -f json -o artifacts/security/python-audit.json
npm audit --prefix frontend --audit-level=high --json > artifacts/security/npm-audit.json
docker run --rm --network none \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/repo \
  -v "$repo_root/.git:/repo/.git:ro" -v "$repo_root/artifacts/security:/reports" \
  zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f \
  git /repo --redact --no-banner --report-format json --report-path /reports/gitleaks.json
# Also scan uncommitted edits, without reading private ignored runtime files.
git diff HEAD --no-ext-diff | docker run --rm -i --network none \
  zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f \
  stdin --redact --no-banner
