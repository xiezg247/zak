# mypy 静态类型检查

zak 采用 **按 workspace package 配置 + 根脚本聚合** 的静态类型检查。

## 配置位置

| 位置 | 职责 |
|------|------|
| `packages/vnpy-common/pyproject.toml` → `[tool.mypy]` | common 全包 |
| `packages/vnpy-skills/pyproject.toml` → `[tool.mypy]` | skills 全包 |
| `packages/vnpy-mcp/pyproject.toml` → `[tool.mypy]` | mcp 全包 |
| `packages/vnpy-tickflow/pyproject.toml` → `[tool.mypy]` | tickflow 全包 |
| `packages/vnpy-llm/pyproject.toml` → `[tool.mypy]` | llm 全包 |
| `packages/vnpy-ashare/pyproject.toml` → `[tool.mypy]` | ashare 全包 |
| `scripts/mypy-check.sh` | 依次跑各 package（CI / 本地统一入口） |

在 package 目录内执行时，`files` 路径相对该包根；`mypy_path` 指向 sibling 包。须通过 `scripts/mypy-check.sh` 或在 `packages/vnpy-ashare` 目录下执行。

## 当前范围

workspace 全部 6 个 package 均已启用 mypy（共 **584** 个源文件）：

| package | 目录 | 文件数 |
|---------|------|--------|
| vnpy-common | `vnpy_common/` | 30 |
| vnpy-skills | `vnpy_skills/` | 9 |
| vnpy-mcp | `vnpy_mcp/` | 11 |
| vnpy-tickflow | `vnpy_tickflow/` | 5 |
| vnpy-llm | `vnpy_llm/` | 78 |
| vnpy-ashare | `vnpy_ashare/` 全包 | 451 |

## 本地运行

```bash
uv sync --extra dev
bash scripts/mypy-check.sh
# 或仅 ashare：
cd packages/vnpy-ashare && ../../.venv/bin/mypy --config-file pyproject.toml
```

## 扩大范围

1. 编辑对应 `packages/*/pyproject.toml` → `[tool.mypy].files`。
2. 在 package 根目录跑 mypy，修完报错后提交。
3. 目录稳定后可加 `[[tool.mypy.overrides]]` 收紧单路径规则。

新增 workspace package：在该包 `pyproject.toml` 增加 `[tool.mypy]`，并在 `scripts/mypy-check.sh` 追加 `run_pkg_mypy packages/<name>`。

## 全局策略

| 选项 | 值 | 原因 |
|------|-----|------|
| `ignore_missing_imports` | `true` | vnpy / PySide 等缺 stub |
| `disallow_untyped_defs` | `false` | 老代码逐步补注解 |
| `follow_imports` | `silent` | 只报告 `files` 内错误 |

## CI

`.github/workflows/lint.yml` → `bash scripts/mypy-check.sh`。

## 新代码约定

- 落在已启用 mypy 目录内的改动：保持 `bash scripts/mypy-check.sh` 通过。
- `QuotesPage` 新增 shell 控件时，同步更新 `ui/quotes/page/shell_attrs.py`。
- `ui/` 新代码建议手写 `Optional` 守卫与返回类型；避免在 `QWidget` 子类上命名 `render()`（与 Qt 绘制 API 冲突）。
- 未启用目录：仍按 [编码规范](./coding-standards.md) 手写注解。
