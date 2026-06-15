# mypy 渐进启用

zak 采用 **按 workspace package 配置 + 根脚本聚合** 的方式逐步引入静态类型检查。

## 配置位置

| 位置 | 职责 |
|------|------|
| `packages/vnpy-ashare/pyproject.toml` → `[tool.mypy]` | ashare 白名单目录、本包 `mypy_path` |
| `scripts/mypy-check.sh` | 依次跑各 package（CI / 本地统一入口） |
| 根 `pyproject.toml` | **不再**放 `[tool.mypy]`；dev 依赖仍含 `mypy` |

在 package 目录内执行时，`files` 路径相对该包根（如 `vnpy_ashare/quotes/core`）；`mypy_path` 指向 sibling 包（如 `../vnpy-common:.`）。

**注意**：必须在 `packages/vnpy-ashare` 目录下执行 mypy（或通过 `scripts/mypy-check.sh`），否则 `files` 白名单可能不生效。

## 当前范围（vnpy-ashare，Phase 1–7）

| 目录 | 说明 | 状态 |
|------|------|------|
| `quotes/*` | core / rank / market / misc / radar | ✅ 严格 |
| `screener/` | 选股全子包 | ✅ 严格 |
| `services/` | 业务门面 | ✅ 严格 |
| `domain/` | 领域模型 | ✅ 严格 |
| `config/` | schema、bridge、preferences | ✅ 严格 |
| `storage/` | app_db、repositories | ✅ 严格 |
| `integrations/` | 含 tickflow、tushare 等（勿单独再列 `integrations/tickflow`，会 duplicate module） | ✅ 严格 |
| `ai/context/` | AI 上下文 | ✅ 严格 |
| `data/` | 行情下载、bar store | ✅ 严格 |
| `jobs/` | 定时任务 | ✅ 严格 |
| `ui/quotes/` | 行情页 Qt UI | ✅ **半严格**（仅 Qt 绑定 5 类 disable） |
| `ui/` 其余 | screener、shell、backtest 等 | ✅ **放宽** |

共 **417** 个源文件。

### Phase 7：`ui/` 放宽规则

Qt / vnpy 绑定层噪声较多：

- **`vnpy_ashare.ui.*`**（除 quotes 外）：暂时关闭 14 类 error code（见 `pyproject.toml`）。
- **`vnpy_ashare.ui.quotes.*`（Phase 7b ✅）**：仅保留 Qt 绑定层 5 类 disable；`assignment` / `union-attr` / `no-any-return` 等已收紧并通过。

**Phase 7c（后续）**：继续收紧 `ui/screener/`、`ui/shell/` 等，并逐步减少 `ui.quotes.*` 的 Qt disable。

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
3. 目录稳定后可加/减 `[[tool.mypy.overrides]]` 收紧单路径规则。

### 建议顺序

```text
Phase 1–6  quotes/*、services/、screener/、domain/、config/、storage/、integrations/、ai/context  ← 严格（195 文件）
Phase 7    data/、jobs/、ai/context/、ui/（417 文件）                         ← 当前
Phase 7b   ui/quotes/ 收紧（40 处类型修复）                                  ← 已完成
Phase 7c   ui/screener/、ui/shell/ 等逐步收紧
Phase 8    vnpy-common 独立 package mypy
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
- `ui/` 新代码仍建议手写 `Optional` 守卫与返回类型，便于 Phase 7b 收紧。
- 未启用目录：仍按 [编码规范](./coding-standards.md) 手写注解。
