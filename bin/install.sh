#!/usr/bin/env bash
# 使用 uv + 国内镜像源安装项目依赖

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MIRROR="${UV_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"

cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "未检测到 uv，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

export UV_INDEX_URL="$MIRROR"

echo "使用镜像源: $MIRROR"
uv sync

echo ""
echo "安装完成。下一步："
echo "  cp .env.example .env"
echo "  uv run python run.py"
echo "  uv run python cli.py job run sync_universe"
