#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN=python3.11
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
  echo "提示: 未找到 python3.11，已回退为 ${PYTHON_BIN}。建议使用 Python 3.11（见 README / .python-version）。" >&2
else
  echo "未找到 python3.11 或 python3，请先安装 Python 3.11。" >&2
  exit 1
fi

"$PYTHON_BIN" -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已复制 .env.example 为 .env，请编辑其中的 SECRET_KEY 等配置。"
fi

python manage.py migrate
python manage.py setup_finance_groups

echo ""
echo "安装完成。接下来请执行："
echo "  source .venv/bin/activate"
echo "  python manage.py createsuperuser   # 使用「电子邮箱」作为登录名"
echo "  python manage.py runserver"
echo ""
echo "在后台将用户加入「财务管理员」或「普通财务」分组以分配权限。"
