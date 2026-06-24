#!/usr/bin/env bash
# UI 分层守卫：禁止 ui/ 直接 import storage / integrations / data.bar_*（workers 暂除外）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI_DIR="$ROOT/packages/vnpy-ashare/vnpy_ashare/ui"

if rg 'from vnpy_ashare\.(storage|integrations|data\.bar_)' "$UI_DIR" --glob '!**/workers/**' -q; then
  echo "UI 分层违规：ui/ 不得直接 import storage / integrations / data.bar_*" >&2
  echo "请经 services/ 或 domain/ 访问；Worker 目录暂排除。" >&2
  rg 'from vnpy_ashare\.(storage|integrations|data\.bar_)' "$UI_DIR" --glob '!**/workers/**' >&2
  exit 1
fi

echo "UI 分层检查通过"
