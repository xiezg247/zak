#!/usr/bin/env bash
# macOS：LightGBM 需要 Homebrew 的 libomp（OpenMP 运行时），无法通过 pip/uv 安装。

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    exit 0
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

lightgbm_ready() {
    uv run python -c "
from vnpy_ashare.quotes.radar.predict.model_paths import lightgbm_unavailable_reason
import sys
sys.exit(0 if lightgbm_unavailable_reason() is None else 1)
" 2>/dev/null
}

if lightgbm_ready; then
    exit 0
fi

if ! command -v brew >/dev/null 2>&1; then
    echo ""
    echo "提示：雷达预测（LightGBM）在 macOS 上需要 OpenMP 运行时。"
    echo "  请先安装 Homebrew：https://brew.sh"
    echo "  然后执行：brew install libomp"
    exit 0
fi

if brew list libomp >/dev/null 2>&1; then
    if lightgbm_ready; then
        exit 0
    fi
    echo ""
    echo "警告：已安装 libomp，但 LightGBM 仍无法加载，请重启终端后重试。"
    exit 0
fi

echo ""
echo "正在安装 macOS OpenMP 运行时（brew install libomp）…"
brew install libomp

if lightgbm_ready; then
    echo "LightGBM 已就绪。"
else
    echo "libomp 已安装；若仍无法导入 LightGBM，请重启终端后再试。"
fi
