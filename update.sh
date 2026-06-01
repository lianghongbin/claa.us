#!/usr/bin/env bash
# Pull latest code from GitHub and restart Docker (for deploy / secondary machines).
#
# Usage:
#   chmod +x update.sh
#   ./update.sh
#
# Optional:
#   GIT_BRANCH=main GIT_REMOTE=origin ./update.sh
#   FINANCE_PORT=8000 ./update.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# shellcheck source=scripts/lib/docker.sh
source "${ROOT}/scripts/lib/docker.sh"

chmod +x update.sh start.sh scripts/*.sh 2>/dev/null || true

OPEN_BROWSER=0 docker_pull_and_restart
