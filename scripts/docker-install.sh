#!/usr/bin/env bash
# One-click install & start the finance app in Docker (macOS / Linux).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${FINANCE_PORT:-8000}"
BASE_URL="http://127.0.0.1:${PORT}/admin/"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@localhost}"

log() { printf '%s\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

require_command() {
  command -v "$1" >/dev/null 2>&1 || return 1
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif require_command docker-compose; then
    docker-compose "$@"
  else
    die "Docker Compose not found. Install Docker Desktop or docker-compose."
  fi
}

ensure_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  log "Docker is not running. Attempting to start…"

  if [[ "$(uname -s)" == "Darwin" ]]; then
    if [[ -d "/Applications/Docker.app" ]]; then
      open -a Docker
    elif require_command brew; then
      log "Installing Docker Desktop via Homebrew (may take a few minutes)…"
      brew install --cask docker
      open -a Docker
    else
      die "Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    fi
  elif require_command systemctl; then
    sudo systemctl start docker 2>/dev/null || true
  fi

  log "Waiting for Docker daemon…"
  local i
  for i in $(seq 1 90); do
    if docker info >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  die "Docker did not become ready. Open Docker Desktop manually and run this script again."
}

random_secret() {
  if require_command openssl; then
    openssl rand -base64 48 | tr -d '/+=' | head -c 64
  else
    python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  fi
}

ensure_env_file() {
  mkdir -p data media backups

  if [[ -f .env ]]; then
    # shellcheck disable=SC1091
    set -a
    source .env
    set +a
    return 0
  fi

  local secret admin_pass
  secret="$(random_secret)"
  admin_pass="$(random_secret | head -c 20)"

  cat > .env <<EOF
SECRET_KEY=${secret}
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${admin_pass}
EOF

  # shellcheck disable=SC1091
  set -a
  source .env
  set +a

  log "Created .env with ADMIN_EMAIL and ADMIN_PASSWORD."
}

migrate_legacy_database() {
  if [[ -f db.sqlite3 && ! -f data/db.sqlite3 ]]; then
    log "Moving existing db.sqlite3 → data/db.sqlite3"
    cp db.sqlite3 data/db.sqlite3
  fi
}

wait_for_app() {
  log "Waiting for the app to respond at ${BASE_URL} …"
  local i
  for i in $(seq 1 60); do
    if curl -sf -o /dev/null "${BASE_URL}" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  die "Service did not become ready. Check: docker compose logs -f web"
}

print_success() {
  log ""
  log "=========================================="
  log "  Finance system is running in Docker"
  log "=========================================="
  log "  URL:      ${BASE_URL}"
  log "  Email:    ${ADMIN_EMAIL}"
  if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
    log "  Password: ${ADMIN_PASSWORD}"
    log "  (also in .env as ADMIN_PASSWORD)"
  else
    log "  Password: see ADMIN_PASSWORD in .env"
  fi
  log ""
  log "  Stop:     docker compose down"
  log "  Logs:     docker compose logs -f web"
  log "  Restart:  docker compose up -d"
  log ""
  log "For auto-start on login: enable"
  log "  Docker Desktop → Settings → Start when you log in"
  log "=========================================="
}

main() {
  log "=== Docker one-click install ==="

  require_command docker || die "Docker CLI not found. Install Docker Desktop first."
  ensure_docker
  ensure_env_file
  migrate_legacy_database

  log "Building and starting containers…"
  compose up -d --build --wait

  wait_for_app

  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "${BASE_URL}" 2>/dev/null || true
  fi

  print_success
}

main "$@"
