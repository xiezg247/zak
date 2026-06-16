# 编码规范

zak 各 package 的代码风格与分层约定。静态类型检查见 [mypy.md](./mypy.md)。

## 分层

```text
UI（pages / widgets / controllers）
    ↓ 经 Service / Engine 访问
Services（QuoteService、BarService、ScreeningService …）
    ↓
Domain / Data / Storage / Integrations
```

- UI **不**直接 import `storage.repositories` 或底层 `bar_store`；K 线读路径统一走 `data/bar_access.py` 或 `BarService`。
- Worker、定时任务与 UI 共用 Service 层，避免在 Worker 内重复业务逻辑。
- AI 上下文：UI / Worker 经 Service 写入 `context_store`；Skills / LLM 只读。

### K 线访问（`bar_access.py`）

| 场景 | 入口 |
|------|------|
| 有 MainEngine | `BarService.load_bars` / `get_overview`（经 `engine_access`） |
| 无 Engine（Worker、单测） | `bar_access` re-export |
| 下载 / 同步 | `bars.py`、`universe.py`（写操作，不经门面） |

## 类型注解

- 已启用 mypy 的 package：改动须保持 `bash scripts/mypy-check.sh` 通过。
- 新函数建议显式参数与返回类型；`Optional` 分支先守卫再使用。
- `ui/` 中避免在 `QWidget` 子类上命名 `render()`（与 Qt 绘制 API 冲突）。
- `QuotesPage` 新增 shell 控件时，同步更新 `ui/quotes/page/shell_attrs.py`。

## 注释

代码以自解释为主；注释仅说明非显而易见的业务规则或跨模块约束。

## Commit

提交信息使用简体中文 Conventional Commits，见根目录 `.cursorrules`。
