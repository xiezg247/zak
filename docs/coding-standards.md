# 编码规范

zak 为 Python 3.10+ / PySide Qt 桌面项目。本文约定代码、注释与分层，与 [架构说明](architecture.md) 互补。

## 工具链

- 行宽 **160**（与 `.editorconfig` 一致）
- 格式化与 lint：**ruff**（`pyproject.toml` → `[tool.ruff]`）
- 类型检查（渐进）：**mypy**（`pyproject.toml` → `[tool.mypy]`，范围见 [mypy 渐进启用](./mypy-rollout.md)）
- 本地检查：`uv run ruff check .` / `uv run ruff format .` / `uv run mypy`
- 测试：`uv run python -m unittest discover -s tests -v`

## 代码风格

### 模块

- 文件顶部使用**一行中文**模块 docstring，说明职责
- 新代码统一 `from __future__ import annotations`
- import 顺序：标准库 → 第三方（vnpy 等）→ 本项目（`vnpy_ashare` / `vnpy_llm` …）

### 命名

- 类：`PascalCase`；函数/变量：`snake_case`
- 私有：单下划线 `_method`；模块内常量：`UPPER_SNAKE`
- Qt 控件：`self.run_btn` 等简短后缀

### 类型

- 公开函数/方法标注参数与返回类型
- 结构化数据优先 `dataclass` / `TypedDict`，避免无约束的 `dict[str, Any]`
- Service 访问使用 `vnpy_ashare.engine_access` 的类型化 getter，避免字符串 `getattr`

## 注释

| 场景 | 要求 |
|------|------|
| 模块 | 一行中文 docstring（必填） |
| 公开 API / Service 方法 | 说明用途；非 obvious 参数需注明 |
| 业务规则 | 中文注释（T+1、交易时段数据源、bar health 状态等） |
| 架构链路 | 模块 docstring 或入口函数说明「谁写 / 谁读 / fallback 条件」（见 `engine_access`、`bar_access`、`context_store`） |
| UI 布局代码 | 一般不写注释 |
| 语言 | 模块/类 docstring 用中文；技术术语可英文（TickFlow、Redis、SubFlow） |

## 分层与封装

```
UI / Worker ──► Service ──► 领域模块（screener / bar_store / …）
                    │
                    └──► context_store（AI 上下文，仅 Service 写入）
```

### 必须遵守

1. **UI 不直连** `app_db`、`bar_store`、`screener/*_store`；经对应 Service 或 Facade
2. **context_store 仅 Service 写入**；LLM / Skill 只读
3. **Engine 访问**统一 `engine_access.get_*_service(main_engine)`
4. **新页面**参考 `ui/quotes/` Controller 拆分，避免 500+ 行 QWidget

### 包边界

| 包 | 职责 |
|----|------|
| `vnpy_ashare/services/` | 业务门面，注入 `AshareEngine` |
| `vnpy_ashare/screener/` | 选股领域逻辑（UI 经 ScreeningService 访问） |
| `vnpy_ashare/ui/` | Qt 视图与 Controller |
| `vnpy_ashare/bar_access.py` | `bar_store` / `app_db` 统一门面（Worker / Service 共用） |
| `vnpy_ashare/ui/styles/` | QSS 按域拆分；对外仍 `from vnpy_ashare.ui.styles import …` |
| `vnpy_llm/ui/styles/` | AI 面板 QSS 按域拆分；对外仍 `from vnpy_llm.ui.styles import …` |
| `skills/` | Agent Skill 实现（根目录脚本域，测试经 `tests/_bootstrap`） |

### Worker

- 看盘 Worker：`ui/quotes/workers/`（K 线 / universe 经 `bar_access`）
- 选股 Worker：`ui/screener/workers/`
- 新代码从上述 feature 子包 import，勿再使用已删除的 `ui/workers/` 聚合层

## Qt 线程

- 使用 `qt_helpers.thread_is_active()` 判断 QThread 状态
- 释放线程用 `release_thread()` / `retain_thread_until_finished()`
- EventEngine 回调中更新 UI 须切回 GUI 线程（Signal 或 `QMetaObject.invokeMethod`）

### import 约定

- **默认模块级 import**；禁止仅为「少写几行」在函数内 import
- **允许函数内 import 的场景**（须在行尾或上一行简短注明原因）：
  - `TYPE_CHECKING` 块（类型注解）
  - 已验证的**循环依赖**（如 `engine_access.get_ashare_engine`、`styles.legacy.apply_legacy_page_style`）
  - **可选重依赖**首次使用时加载（`redis`、`tushare`、`openai`、`vnpy_ctabacktester` 等）
  - **vnpy / Qt 插件**在部分 headless 环境不可用

### 避免循环 import

- 图表 Tab 索引等共享常量放 `ui/quotes/chart/tab_indices.py`，勿让 controller 从 `chart.panel` 反向 import

## 提交

Commit message 使用简体中文 Conventional Commits，见根目录 `.cursorrules`。
