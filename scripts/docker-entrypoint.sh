#!/usr/bin/env bash
set -euo pipefail
cd /app

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — set SECRET_KEY before production use." >&2
fi

mkdir -p /data media backups

python manage.py migrate --noinput
python manage.py setup_finance_groups
python manage.py ensure_superuser

exec python manage.py runserver 0.0.0.0:8000
