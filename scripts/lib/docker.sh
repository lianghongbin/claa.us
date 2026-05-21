# Shared helpers for Docker scripts. Source from other scripts; do not execute directly.
if [[ -n "${_CLAA_DOCKER_LIB_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_CLAA_DOCKER_LIB_LOADED=1

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

load_env_port() {
  FINANCE_PORT="${FINANCE_PORT:-8000}"
  if [[ -f .env ]]; then
    # shellcheck disable=SC1091
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    FINANCE_PORT="${FINANCE_PORT:-8000}"
  fi
  export FINANCE_PORT
  BASE_URL="http://127.0.0.1:${FINANCE_PORT}/admin/"
  export BASE_URL
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

compose_down() {
  log "Stopping existing containers (docker compose down)…"
  compose down --remove-orphans 2>/dev/null || true
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'claa-finance'; then
    log "Removing container claa-finance…"
    docker rm -f claa-finance 2>/dev/null || true
  fi
}

free_host_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  log "Port ${port} is in use (PID: ${pids}). Releasing…"
  # shellcheck disable=SC2086
  kill ${pids} 2>/dev/null || true
  sleep 2
  pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill -9 ${pids} 2>/dev/null || true
    sleep 1
  fi
  if lsof -ti "tcp:${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    die "Could not free port ${port}. Stop the process manually and retry."
  fi
  log "Port ${port} is now free."
}

update_code_from_github() {
  local branch="${GIT_BRANCH:-main}"
  local remote="${GIT_REMOTE:-origin}"

  if [[ ! -d .git ]]; then
    die "Not a git repo. Clone first: git clone https://github.com/lianghongbin/claa.us.git"
  fi

  require_command git || die "git not found."
  log "Updating code (${remote}/${branch})…"
  git fetch "${remote}" "${branch}"
  git checkout "${branch}" 2>/dev/null || git checkout -b "${branch}" "${remote}/${branch}"
  git reset --hard "${remote}/${branch}"
  log "Code is now at: $(git rev-parse --short HEAD) $(git log -1 --format='%s')"
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
  ADMIN_EMAIL="${ADMIN_EMAIL:-admin@localhost}"

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
ALLOWED_HOSTS=127.0.0.1,localhost,fin.skyvl.com
CSRF_TRUSTED_ORIGINS=https://fin.skyvl.com
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${admin_pass}
FINANCE_PORT=${FINANCE_PORT:-8000}
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
  log "Waiting for the app at ${BASE_URL} …"
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
  ADMIN_EMAIL="${ADMIN_EMAIL:-admin@localhost}"
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
  log "  Update:   ./start.sh"
  log "=========================================="
}

docker_install_and_start() {
  require_command docker || die "Docker CLI not found."
  ensure_docker
  ensure_env_file
  load_env_port
  migrate_legacy_database

  log "Building and starting containers…"
  compose up -d --build --wait
  wait_for_app

  if [[ "${OPEN_BROWSER:-1}" == "1" && "$(uname -s)" == "Darwin" ]]; then
    open "${BASE_URL}" 2>/dev/null || true
  fi

  print_success
}
