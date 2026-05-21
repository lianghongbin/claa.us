#!/usr/bin/env bash
# One-click install & start (first-time setup, no git pull).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=lib/docker.sh
source "${ROOT}/scripts/lib/docker.sh"

main() {
  log "=== Docker one-click install ==="
  load_env_port
  compose_down
  free_host_port "${FINANCE_PORT}"
  docker_install_and_start
}

main "$@"
