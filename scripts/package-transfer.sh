#!/usr/bin/env bash
# 打包项目以便复制到另一台 Mac（不含 .venv，可选包含数据库与附件）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PARENT="$(dirname "$ROOT")"
NAME="$(basename "$ROOT")"
STAMP="$(date +%Y%m%d)"
OUT="${PARENT}/${NAME}-transfer-${STAMP}.zip"

INCLUDE_DB=0
INCLUDE_MEDIA=0
for arg in "$@"; do
  case "$arg" in
    --with-db) INCLUDE_DB=1 ;;
    --with-media) INCLUDE_MEDIA=1 ;;
    -h | --help)
      echo "用法: $0 [--with-db] [--with-media]"
      echo "  --with-db    包含 db.sqlite3（带上现有业务数据）"
      echo "  --with-media 包含 media/（凭证附件）"
      exit 0
      ;;
  esac
done

EXCLUDES=(
  ".venv/*"
  "__pycache__/*"
  "*.pyc"
  ".git/*"
  "staticfiles/*"
  ".DS_Store"
  "*.log"
)
[[ "$INCLUDE_DB" == 1 ]] || EXCLUDES+=("db.sqlite3")
[[ "$INCLUDE_MEDIA" == 1 ]] || EXCLUDES+=("media/*")

ZIP_ARGS=(-r "$OUT" "$NAME" -x "${EXCLUDES[@]}")
cd "$PARENT"
zip "${ZIP_ARGS[@]}" >/dev/null

echo "已生成: $OUT"
echo "在另一台 Mac 上解压后："
echo "  cd $NAME"
echo "  ./scripts/install.sh"
echo "  ./scripts/run.sh"
echo "Or double-click start.command in Finder"
