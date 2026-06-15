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

# 按依赖顺序（common → skills/mcp/tickflow → llm → ashare）
run_pkg_mypy packages/vnpy-common
run_pkg_mypy packages/vnpy-skills
run_pkg_mypy packages/vnpy-mcp
run_pkg_mypy packages/vnpy-tickflow
run_pkg_mypy packages/vnpy-llm
run_pkg_mypy packages/vnpy-ashare
