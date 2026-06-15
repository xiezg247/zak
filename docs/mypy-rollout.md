# mypy 渐进启用

zak 采用 **按 workspace package 配置 + 根脚本聚合** 的方式逐步引入静态类型检查。

## 配置位置

| 位置 | 职责 |
|------|------|
| `packages/vnpy-ashare/pyproject.toml` → `[tool.mypy]` | ashare 白名单目录、本包 `mypy_path` |
| `scripts/mypy-check.sh` | 依次跑各 package（CI / 本地统一入口） |
| 根 `pyproject.toml` | **不再**放 `[tool.mypy]`；dev 依赖仍含 `mypy` |

在 package 目录内执行时，`files` 路径相对该包根（如 `vnpy_ashare/quotes/core`）；`mypy_path` 指向 sibling 包（如 `../vnpy-common:.`）。

## 当前范围（vnpy-ashare，Phase 1–6）

| 目录 | 说明 | 状态 |
|------|------|------|
| `quotes/*` | core / rank / market / misc / radar | ✅ |
| `screener/` | 选股全子包（含 data、dimensions、recipe、run…） | ✅ |
| `services/` | 业务门面（含 analysis、signals） | ✅ |
| `domain/` | 领域模型、交易日历、symbol 等 | ✅ |
| `config/` | schema、bridge、preferences、fonts | ✅ |
| `storage/` | app_db、repositories | ✅ |
| `integrations/tickflow/` | TickFlow 行情适配 | ✅ |
| `ai/context/` | AI 上下文组装 | ✅ |

共 **195** 个源文件。

## 本地运行

```bash
uv sync --extra dev
bash scripts/mypy-check.sh
# 或仅 ashare：
cd packages/vnpy-ashare && ../../.venv/bin/mypy --config-file pyproject.toml
```

## 扩大范围（vnpy-ashare）

1. 编辑 `packages/vnpy-ashare/pyproject.toml` → `[tool.mypy].files`，追加子包路径。
2. 在 package 根目录跑 mypy，修完报错后提交。
3. 目录稳定后可加 `[[tool.mypy.overrides]]` 收紧单路径规则。

### 建议顺序

```text
Phase 1–3  quotes/*
Phase 4    services/
Phase 5–6  screener/、domain/、config/、storage/、integrations/tickflow、ai/context  ← 当前（195 文件）
Phase 7    ui/quotes/（Qt / types-PySide6）
Phase 8    data/、integrations/ 其余、jobs/
```

## 新增 workspace package

1. 在该包 `pyproject.toml` 增加 `[tool.mypy]`（可先只设 `files = ["<包名>"]`）。
2. 在 `scripts/mypy-check.sh` 追加 `run_pkg_mypy packages/<name>`。

## 全局策略（各 package 默认一致）

| 选项 | 值 | 原因 |
|------|-----|------|
| `ignore_missing_imports` | `true` | vnpy / PySide 等缺 stub |
| `disallow_untyped_defs` | `false` | 老代码逐步补注解 |
| `follow_imports` | `silent` | 只报告 `files` 内错误 |

## CI

`.github/workflows/lint.yml` → `bash scripts/mypy-check.sh`。

## 新代码约定

- 落在 **已启用 mypy 目录** 内的改动：保持 `bash scripts/mypy-check.sh` 通过。
- 未启用目录：仍按 [编码规范](./coding-standards.md) 手写注解。
