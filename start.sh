#!/usr/bin/env bash
# One-click update & start: stop containers, pull latest code, free port, Docker up.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# shellcheck source=scripts/lib/docker.sh
source "${ROOT}/scripts/lib/docker.sh"

main() {
  log "=== Finance system update & start ==="

  load_env_port
  require_command docker || die "Docker CLI not found."
  ensure_docker

  compose_down
  free_host_port "${FINANCE_PORT}"

  update_code_from_github

  chmod +x start.sh scripts/*.sh 2>/dev/null || true

  OPEN_BROWSER="${OPEN_BROWSER:-1}" docker_install_and_start
}

main "$@"
