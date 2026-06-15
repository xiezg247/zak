#!/usr/bin/env bash
# 按 workspace package 运行 mypy；各包配置见 packages/*/pyproject.toml → [tool.mypy]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MYPY="${ROOT}/.venv/bin/mypy"
if [[ ! -x "$MYPY" ]]; then
  echo "mypy: 请先 uv sync --extra dev" >&2
  exit 1
fi

run_pkg_mypy() {
  local pkg_dir="$1"
  local config="$ROOT/$pkg_dir/pyproject.toml"
  if ! grep -q '^\[tool\.mypy\]' "$config" 2>/dev/null; then
    return 0
  fi
  echo "==> mypy: $pkg_dir"
  (
    cd "$ROOT/$pkg_dir"
    "$MYPY" --config-file pyproject.toml
  )
}

# 新增 package 时在此追加（依赖顺序：common 先于 ashare）
run_pkg_mypy packages/vnpy-common
run_pkg_mypy packages/vnpy-ashare
