#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=/dev/null
source .venv/bin/activate
if [[ "${1:-}" == "--latest" ]]; then
  exec python manage.py restore_database --latest
fi
if [[ -z "${1:-}" ]]; then
  echo "Usage: $0 --latest"
  echo "       $0 <backup-filename-in-backups/>"
  exit 1
fi
exec python manage.py restore_database "$1"
