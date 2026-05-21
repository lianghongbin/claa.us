#!/usr/bin/env bash
# 在本机启动开发服务器（另一台 Mac 首次请先运行 ./scripts/install.sh）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "未检测到虚拟环境，正在执行首次安装…"
  ./scripts/install.sh
fi

# shellcheck source=/dev/null
source .venv/bin/activate

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已生成 .env，请按需修改 SECRET_KEY 等配置。"
fi

python manage.py migrate --noinput
python manage.py setup_finance_groups

if ! python manage.py shell -c "from django.contrib.auth import get_user_model; raise SystemExit(0 if get_user_model().objects.exists() else 1)" 2>/dev/null; then
  echo ""
  echo "尚未创建管理员账号，请按提示输入电子邮箱与密码："
  python manage.py createsuperuser
  echo ""
fi

HOST="${FINANCE_HOST:-127.0.0.1}"
PORT="${FINANCE_PORT:-8000}"
URL="http://${HOST}:${PORT}/admin/"

echo ""
echo "财务系统启动中 → ${URL}"
echo "按 Ctrl+C 停止服务。"
echo ""

if [[ "$(uname -s)" == "Darwin" ]] && [[ "${FINANCE_OPEN_BROWSER:-1}" == "1" ]]; then
  (sleep 1.5 && open "${URL}") >/dev/null 2>&1 &
fi

exec python manage.py runserver "${HOST}:${PORT}"
