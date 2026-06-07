#!/usr/bin/env bash
# 启动 QuestDB（VeighNa vnpy_questdb 需要 8812 + 9000 端口）
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d questdb
echo "QuestDB 已启动: PGWire localhost:8812, HTTP localhost:9000"
echo "Web Console: http://localhost:9000"
