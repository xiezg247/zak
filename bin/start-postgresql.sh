#!/usr/bin/env bash
# 启动 PostgreSQL（VeighNa vnpy_postgresql 需要 5432 端口）
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d postgresql
echo "PostgreSQL 已启动: localhost:5432 (DB: zak, 用户: zak)"
