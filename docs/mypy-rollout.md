# mypy 渐进启用

zak 采用 **白名单目录 + CI 守门** 的方式逐步引入静态类型检查，避免一次性全仓 strict 带来的巨大改造成本。

## 当前范围（Phase 1）

| 目录 | 说明 |
|------|------|
| `packages/vnpy-ashare/vnpy_ashare/quotes/core/` | QuoteSnapshot、Provider、Redis、enrich |
| `packages/vnpy-ashare/vnpy_ashare/quotes/rank/` | 排行 catalog / engine / scope |

配置位于根目录 `pyproject.toml` → `[tool.mypy]` 的 `files` 列表。

## 本地运行

```bash
uv sync --extra dev
uv run mypy
```

仅对 `files` 内模块报错；依赖模块通过 `follow_imports = "silent"` 跟进分析，但不向外扩散错误。

## 扩大范围

1. 在 `[tool.mypy].files` 追加目标路径（建议每次一个子包，如 `quotes/market`、`quotes/misc`）。
2. 本地执行 `uv run mypy`，修完该目录内报错后再提交。
3. 新模块默认保持 `disallow_untyped_defs = false`；目录稳定后可对该路径加 `[[tool.mypy.overrides]]` 收紧。

### 建议顺序

```text
Phase 1  quotes/core、quotes/rank          ← 当前
Phase 2  quotes/market、quotes/misc
Phase 3  quotes/radar
Phase 4  screener/data、services/（按域拆分）
Phase 5  ui/quotes/（Qt 依赖多，需 types-PySide6 或局部 ignore）
```

## 全局策略

| 选项 | 值 | 原因 |
|------|-----|------|
| `ignore_missing_imports` | `true` | vnpy / PySide / 部分第三方无完整 stub |
| `disallow_untyped_defs` | `false` | 老代码逐步补注解，不在扩 scope 时一刀切 |
| `follow_imports` | `silent` | 只报告 `files` 内错误，便于分阶段推进 |

## CI

`.github/workflows/lint.yml` 的 **mypy** job 与 ruff 并列；`files` 范围内有类型错误则 PR 失败。

## 新代码约定

- 落在 **已启用 mypy 目录** 内的改动：保持 `uv run mypy` 通过；公开函数补全参数与返回类型。
- 落在 **未启用目录**：仍按 [编码规范](./coding-standards.md) 手写注解，待该目录纳入 `files` 后再由 mypy 强制。
