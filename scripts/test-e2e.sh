#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export UNIFLOW_E2E=1
npm run test:e2e --prefix frontend -- "$@"
