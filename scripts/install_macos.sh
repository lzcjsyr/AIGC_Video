#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
PYTHON_EXE="$VENV_DIR/bin/python"

require_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "缺少 $name。"
    echo "$hint"
    exit 1
  fi
}

cd "$REPO_ROOT"

require_command "python3" "请安装 Python 3.11+。推荐使用 Homebrew: brew install python"
require_command "ffmpeg" "请安装 FFmpeg: brew install ffmpeg"
require_command "node" "请安装 Node.js 22 LTS。推荐使用 Homebrew: brew install node"
require_command "npm" "请确认 npm 已随 Node.js 安装并加入 PATH。"

if [ ! -x "$PYTHON_EXE" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON_EXE" -m pip install --upgrade pip
"$PYTHON_EXE" -m pip install -e "$REPO_ROOT"
npm ci --prefix "$REPO_ROOT/core/infra/motion" --omit=dev --no-audit --no-fund
echo "HTML 动画需要 Chrome；非标准安装位置请设置 AIGC_BROWSER_PATH。"

if [ ! -f "$REPO_ROOT/.env" ] && [ -f "$REPO_ROOT/.env.example" ]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo "已生成 .env，请填入 API 密钥。"
fi

"$PYTHON_EXE" -m core.dependency_check --repo-root "$REPO_ROOT"

echo
echo "安装完成。启动程序："
echo "$PYTHON_EXE -m cli"
