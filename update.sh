#!/usr/bin/env bash
# 从 GitHub 拉取最新代码，重新编译 Docker 镜像并重启应用。
#
# 用法（在已 git clone 的项目目录）:
#   chmod +x update.sh
#   ./update.sh
#
# 可选:
#   GIT_BRANCH=main  GIT_REMOTE=origin  FINANCE_PORT=8000
#   DOCKER_BUILD_NO_CACHE=1
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# shellcheck source=scripts/lib/docker.sh
source "${ROOT}/scripts/lib/docker.sh"

chmod +x update.sh start.sh scripts/*.sh 2>/dev/null || true

log "=========================================="
log "  Finance: pull code & restart Docker"
log "=========================================="

OPEN_BROWSER=0 main_update

log "After update: hard-refresh browser (Cmd+Shift+R) or purge CDN cache."
