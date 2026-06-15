# mypy 渐进启用

zak 采用 **按 workspace package 配置 + 根脚本聚合** 的方式逐步引入静态类型检查。

## 配置位置

| 位置 | 职责 |
|------|------|
| `packages/vnpy-common/pyproject.toml` → `[tool.mypy]` | common 全包（`vnpy_common`） |
| `packages/vnpy-skills/pyproject.toml` → `[tool.mypy]` | skills 全包 |
| `packages/vnpy-mcp/pyproject.toml` → `[tool.mypy]` | mcp 全包 |
| `packages/vnpy-tickflow/pyproject.toml` → `[tool.mypy]` | tickflow 全包 |
| `packages/vnpy-llm/pyproject.toml` → `[tool.mypy]` | llm 全包 |
| `packages/vnpy-ashare/pyproject.toml` → `[tool.mypy]` | ashare 白名单目录、本包 `mypy_path` |
| `scripts/mypy-check.sh` | 依次跑各 package（CI / 本地统一入口） |
| 根 `pyproject.toml` | **不再**放 `[tool.mypy]`；dev 依赖仍含 `mypy` |

在 package 目录内执行时，`files` 路径相对该包根（如 `vnpy_ashare/quotes/core`）；`mypy_path` 指向 sibling 包（如 `../vnpy-common:.`）。

**注意**：必须在 `packages/vnpy-ashare` 目录下执行 mypy（或通过 `scripts/mypy-check.sh`），否则 `files` 白名单可能不生效。

## 当前范围

**workspace 全部 6 个 package 均已启用 mypy**（共 **584** 个源文件）。

### vnpy-common（Phase 8）

| 目录 | 说明 | 状态 |
|------|------|------|
| `vnpy_common/` | 路径、AI 协议、终端主题与 UI 组件 | ✅ 严格 |

共 **30** 个源文件。

### vnpy-skills / vnpy-mcp / vnpy-tickflow / vnpy-llm（Phase 9）

| package | 目录 | 文件数 | 状态 |
|---------|------|--------|------|
| vnpy-skills | `vnpy_skills/` | 9 | ✅ 严格 |
| vnpy-mcp | `vnpy_mcp/` | 11 | ✅ 严格 |
| vnpy-tickflow | `vnpy_tickflow/` | 5 | ✅ 严格 |
| vnpy-llm | `vnpy_llm/` | 78 | ✅ 严格 |

`mypy_path`：skills / mcp / tickflow 指向 `../vnpy-common`；llm 另含 `../vnpy-skills`、`../vnpy-mcp`。

### vnpy-ashare（Phase 1–7e，Phase 10 全包）

| 目录 | 说明 | 状态 |
|------|------|------|
| `quotes/*` | core / rank / market / misc / radar | ✅ 严格 |
| `screener/` | 选股全子包（业务层） | ✅ 严格 |
| `services/` | 业务门面 | ✅ 严格 |
| `domain/` | 领域模型 | ✅ 严格 |
| `config/` | schema、bridge、preferences | ✅ 严格 |
| `storage/` | app_db、repositories | ✅ 严格 |
| `integrations/` | 含 tickflow、tushare 等（勿单独再列 `integrations/tickflow`，会 duplicate module） | ✅ 严格 |
| `ai/` | 上下文、llm_bridge、UI 浮动动作 | ✅ 严格 |
| `app/` | 启动器、引擎、bootstrap | ✅ 严格 |
| `backtest/` | 回测引擎与批量运行 | ✅ 严格 |
| `commands/` | CLI 子命令 | ✅ 严格 |
| `data/` | 行情下载、bar store | ✅ 严格 |
| `jobs/` | 定时任务 | ✅ 严格 |
| `scheduler/` | APScheduler 配置与管理 | ✅ 严格 |
| `ui/` | Qt 桌面 UI 全包 | ✅ **严格**（Phase 7e） |

共 **451** 个源文件；`vnpy_ashare/` 顶層子包已全部纳入白名单。

### Phase 7：`ui/` 半严格 → 全严格（7e）

- **Phase 7b–7c**：收紧 `assignment` / `union-attr` / `no-any-return` 等（40 + 25 处修复）。
- **Phase 7d ✅**：引入 dev 依赖 `types-PySide6`；去掉 `override`、`call-overload`、`arg-type`、`misc` disable；修复 Qt 模型 override、`QWidget.render` 命名冲突（`render_panel` / `render_reports` 等）、Signal 类型等约 56 处。
- **Phase 7e ✅**：去掉 `attr-defined` disable；`QuotesPageShellAttrs` mixin 声明 shell 赋值的 ~60 个 UI 属性；Protocol / 子类 / `cast(Any, …)` 处理 pyqtgraph、QStyleOptionViewItem stub 缺口、Worker 引擎接口等约 530 处。

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
Phase 1–6  quotes/*、services/、screener/、domain/、config/、storage/、integrations/、ai/context  ← 严格
Phase 7    data/、jobs/、ui/ 纳入白名单（417 文件）                                              ← 已完成
Phase 7b   ui/quotes/ 收紧（40 处）                                                             ← 已完成
Phase 7c   ui 其余子包收紧（25 处）；移除 ui.* 全量 14 类 disable                               ← 已完成
Phase 7d   types-PySide6；去掉 override/call-overload/arg-type/misc（仅留 attr-defined）  ← 已完成
Phase 7e   去掉 attr-defined；QuotesPage shell 属性 mixin + Qt/pyqtgraph Protocol  ← 已完成
Phase 8    vnpy-common 独立 package mypy（30 文件）                                    ← 已完成
Phase 9    vnpy-skills / vnpy-mcp / vnpy-tickflow / vnpy-llm 全包 mypy（103 文件）   ← 已完成
Phase 10   vnpy-ashare 余下 app/backtest/commands/scheduler/ai 全包（451 文件）     ← 已完成
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
- `QuotesPage` 新增 shell 控件时，同步更新 `ui/quotes/page/shell_attrs.py`。
- `ui/` 新代码建议手写 `Optional` 守卫与返回类型；避免在 `QWidget` 子类上命名 `render()`（与 Qt 绘制 API 冲突）。
- 未启用目录：仍按 [编码规范](./coding-standards.md) 手写注解。
