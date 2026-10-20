#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
chat_id="${UNIFLOW_TELEGRAM_CHAT_ID:-}"
if [[ -z "$chat_id" && -f .local/telegram/chat_id ]]; then
  chat_id="$(cat .local/telegram/chat_id)"
fi
if [[ -z "$chat_id" ]]; then
  echo "Set UNIFLOW_TELEGRAM_CHAT_ID or private .local/telegram/chat_id." >&2
  exit 1
fi
if [[ "$#" -eq 0 ]]; then
  set -- --check
fi
exec python3 integrations/telegram_bot.py --chat-id "$chat_id" --status-file "$repo_root/.local/telegram/status.json" "$@"
