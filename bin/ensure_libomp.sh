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

python_machine() {
    uv run python -c "import platform; print(platform.machine())" 2>/dev/null || echo ""
}

dylib_machine() {
    local lib="$1"
    if [[ ! -f "$lib" ]]; then
        echo ""
        return
    fi
    if file "$lib" 2>/dev/null | grep -q arm64; then
        echo "arm64"
    elif file "$lib" 2>/dev/null | grep -q x86_64; then
        echo "x86_64"
    else
        echo ""
    fi
}

arm64_brew() {
    if [[ -x /opt/homebrew/bin/brew ]]; then
        echo "/opt/homebrew/bin/brew"
    fi
}

warn_libomp_still_broken() {
    local py_arch="$1"
    local brew_lib="${2:-}"
    local omp_arch="${3:-}"

    echo ""
    echo "警告：已安装 libomp，但 LightGBM 仍无法加载。"
    if [[ "$py_arch" == "arm64" && "$omp_arch" == "x86_64" ]]; then
        echo "  原因：Python/LightGBM 为 arm64，但当前 Homebrew（$(brew --prefix 2>/dev/null || echo /usr/local)）提供的是 x86_64 版 libomp。"
        echo "  LightGBM 会从 /opt/homebrew/opt/libomp/lib/libomp.dylib 加载 OpenMP。"
        echo ""
        echo "  修复：安装 Apple Silicon 版 Homebrew 后执行"
        echo "    /opt/homebrew/bin/brew install libomp"
        echo "  安装脚本：https://brew.sh"
    elif [[ "$py_arch" == "arm64" && ! -f /opt/homebrew/opt/libomp/lib/libomp.dylib ]]; then
        echo "  原因：未找到 arm64 所需的 /opt/homebrew/opt/libomp/lib/libomp.dylib。"
        local abrew
        abrew="$(arm64_brew)"
        if [[ -n "$abrew" ]]; then
            echo "  可执行：$abrew install libomp"
        else
            echo "  请先安装 Apple Silicon 版 Homebrew：https://brew.sh"
            echo "  然后执行：/opt/homebrew/bin/brew install libomp"
        fi
    elif [[ -n "$brew_lib" ]]; then
        echo "  已安装：$brew_lib（$omp_arch）"
        echo "  请确认其与 Python（$py_arch）架构一致；不一致时需安装对应架构的 libomp。"
    else
        echo "  请重启终端后重试；若仍失败，请检查 lightgbm 与 libomp 架构是否一致。"
    fi
}

try_install_arm64_libomp() {
    local abrew
    abrew="$(arm64_brew)"
    if [[ -z "$abrew" ]]; then
        return 1
    fi
    if ! "$abrew" list libomp >/dev/null 2>&1; then
        echo ""
        echo "检测到 arm64 Python，正在通过 Apple Silicon Homebrew 安装 libomp…"
        "$abrew" install libomp
    fi
    lightgbm_ready
}

if lightgbm_ready; then
    exit 0
fi

PY_ARCH="$(python_machine)"

if [[ "$PY_ARCH" == "arm64" ]] && try_install_arm64_libomp; then
    echo "LightGBM 已就绪。"
    exit 0
fi

if ! command -v brew >/dev/null 2>&1; then
    echo ""
    echo "提示：雷达预测（LightGBM）在 macOS 上需要 OpenMP 运行时。"
    echo "  请先安装 Homebrew：https://brew.sh"
    if [[ "$PY_ARCH" == "arm64" ]]; then
        echo "  arm64 Python 请使用 Apple Silicon 版：/opt/homebrew/bin/brew install libomp"
    else
        echo "  然后执行：brew install libomp"
    fi
    exit 0
fi

if brew list libomp >/dev/null 2>&1; then
    if lightgbm_ready; then
        exit 0
    fi
    BREW_LIB="$(brew --prefix libomp)/lib/libomp.dylib"
    warn_libomp_still_broken "$PY_ARCH" "$BREW_LIB" "$(dylib_machine "$BREW_LIB")"
    exit 0
fi

echo ""
echo "正在安装 macOS OpenMP 运行时（brew install libomp）…"
brew install libomp

if lightgbm_ready; then
    echo "LightGBM 已就绪。"
else
    BREW_LIB="$(brew --prefix libomp)/lib/libomp.dylib"
    warn_libomp_still_broken "$PY_ARCH" "$BREW_LIB" "$(dylib_machine "$BREW_LIB")"
fi
