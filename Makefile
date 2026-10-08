# zak — 常用开发与运维入口
# 用法: make <target>   或  make help

UV       ?= uv
PYTHON   ?= $(UV) run python
CLI      := $(PYTHON) cli.py
COMPOSE  ?= docker compose

.DEFAULT_GOAL := help

.PHONY: help install sync sync-dev run \
	pg-up pg-down pg-logs \
	db-upgrade db-status \
	sync-universe quotes-collect skills-sync \
	test lint format check

help: ## 显示可用目标
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ── 环境 ──────────────────────────────────────────

install: ## 安装依赖（bin/install.sh）
	bash bin/install.sh

sync: ## uv sync（运行时依赖）
	$(UV) sync

sync-dev: ## uv sync --extra dev（含 pytest / ruff / mypy）
	$(UV) sync --extra dev

run: ## 启动 GUI
	$(PYTHON) run.py

# ── PostgreSQL ────────────────────────────────────

pg-up: ## 启动本地 PostgreSQL（Docker）
	bash bin/start-postgresql.sh

pg-down: ## 停止本地 PostgreSQL
	$(COMPOSE) stop postgresql

pg-logs: ## 查看 PostgreSQL 日志
	$(COMPOSE) logs -f postgresql

db-upgrade: ## 执行 Alembic upgrade head
	$(CLI) db upgrade

db-status: ## 显示当前数据库连接与驱动
	$(CLI) db status

# ── 数据 / 运维 ───────────────────────────────────

sync-universe: ## 同步全 A 股列表
	$(CLI) job run sync_universe

quotes-collect: ## 采集行情到 Redis（单次）
	$(CLI) job run collect_quotes --force

skills-sync: ## 同步 Agent Skills
	$(CLI) skills sync

# ── 质量 ──────────────────────────────────────────

test: ## 运行单元测试
	$(UV) run pytest tests/ -q

lint: ## ruff check
	$(UV) run ruff check .

format: ## ruff format
	$(UV) run ruff format .

check: lint test ## lint + test
