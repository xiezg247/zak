# 看盘页个股笔记

## 1. 功能概述

同一只标的支持三种笔记形态，经 `NoteService` 统一读写；摘要注入看盘 AI 上下文，Skill 可读备忘/流水/报告。

| 形态 | 代号 | 交互 | 存储 |
|------|------|------|------|
| 流水 | `entry` | 列表 + 底部输入，`Ctrl+Enter` 追加 | 每票多条，只追加 |
| 备忘 | `memo` | Markdown 编辑/预览，防抖自动保存 | 每票一行，upsert |
| 分析报告 | `report` | 多篇历史，Markdown 只读 + 删除 | `stock_analysis_reports`（含 AI 对话、**投研团队** `source_scope=team_analysis`） |

### 入口

| 入口 | 行为 |
|------|------|
| 自选右侧 `StockNotePanel` | 备忘 + 流水（可折叠） |
| 笔记 → 笔记中心（`Ctrl+Shift+N`） | 左侧标的列表 + 备忘 / 流水 / 报告 / 计划 / **交易流水** Tab |
| 自选「笔记中心」按钮 | 打开笔记中心并定位当前标的 |
| 个股分析 | 「保存分析报告」「历史报告」→ 笔记中心报告 Tab |
| AI 对话气泡右键 | 存为分析报告、追加到流水 |

### 边界

| 项 | 约定 |
|----|------|
| **流水** vs **交易流水** | 「流水」Tab = `stock_note_entries` 自由文本；「**交易流水**」Tab = `trade_journal` 结构化（可编辑 / 删除），见 [trading-plan-journal.md §3.3](./trading-plan-journal.md#33-ui-入口查看--编辑--删除) |
| Panel 范围 | 自选页（`show_stock_notes=True` 且 `show_kline=True`） |
| 笔记中心 | 全局，不依赖当前看盘页 |
| 存储 | `~/.vntrader/zak.db` |
| 与持仓附注 | **不合并** `watchlist_positions.notes` |

---

## 2. 布局

### 2.1 自选页

```text
┌─ 右侧图表区（ChartSectionPanel）────────────┐
│  行情头                                       │
│  ┌ 日 K / 分 K ────────────────────────┐   │
│  └─────────────────────────────────────┘   │
│  ▼ 笔记 StockNotePanel（可折叠）              │
│  ┌ [备忘] [流水] ─────────────────────┐   │
│  └─────────────────────────────────────┘   │
└────────────────────────────────────────────┘
```

### 2.2 笔记中心

```text
┌ 搜索 + 筛选 ─┬ 标题 + [备忘|流水|报告|计划|交易流水] Tab ─┐
│ 标的列表      │  编辑 / 列表 / 报告 / 结构化流水明细         │
└──────────────┴────────────────────────────────────────────┘
```

路径：`ui/features/notes_center/`（`widget.py`、`memo_view.py`、`reports_view.py`）；结构化流水复用 `ui/quotes/watchlist_positions/trade_journal_manage_view.py`。

---

## 3. 数据模型

```sql
CREATE TABLE IF NOT EXISTS stock_note_memos (...);
CREATE TABLE IF NOT EXISTS stock_note_entries (...);
CREATE TABLE IF NOT EXISTS stock_analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    source_scope TEXT NOT NULL DEFAULT '',   -- 如 team_analysis / ai_dialog
    context_json TEXT NOT NULL DEFAULT '',   -- 团队评分等结构化上下文
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

领域模型：`domain/stock_note.py` — `StockNoteMemo`、`StockNoteEntry`、`StockAnalysisReport`、`StockNoteBundle`、`StockNoteIndexRow`。

---

## 4. 模块结构

```text
domain/stock_note.py
storage/repositories/stock_notes.py
storage/repositories/stock_analysis_reports.py
services/note.py
ui/quotes/stock_notes/          # 自选 Panel
├── panel.py
├── memo_tab.py
├── journal_tab.py
├── ai_assist.py                # AI 整理 / 扩写 Worker
ui/features/notes_center/
ui/features/stock_analysis/save_report_dialog.py
skills/vnpy_notes_skill.py
```

---

## 5. Service 与 Skill

### 5.1 NoteService

| 方法 | 说明 |
|------|------|
| `get_bundle` | memo + entries |
| `upsert_memo` / `append_entry` | 备忘 / 流水写入 |
| `list_reports` / `create_report` / `delete_report` | 分析报告 |
| `list_index_rows` | 笔记中心左侧索引 |
| `build_ai_snippet` | AI 上下文（备忘 + 流水 + 最近 3 篇报告摘要） |
| `export_symbol_markdown` | 导出含报告章节 |

### 5.2 Skill（`vnpy-notes`）

| 工具 | 说明 |
|------|------|
| `get_stock_notes` | memo + entries + 报告摘要 |
| `append_stock_note_entry` | 追加流水 |
| `update_stock_note_memo` | 更新备忘 |
| `delete_stock_note_entry` / `clear_stock_notes` | 删除 |
| `list_stock_analysis_reports` | 列出报告 |
| `get_stock_analysis_report` | 报告全文 |

---

## 6. 笔记区 AI 增强

依赖 `vnpy-llm` + `.env` 中 `LLM_API_KEY`；单次非流式调用（`complete_chat_completion`）。

| 位置 | 流水「AI 整理」 | 备忘「AI 扩写」 | 附带行情 |
|------|----------------|----------------|----------|
| 自选 `StockNotePanel` | ✅ | ✅ | ✅（看盘 `quote_map`） |
| 笔记中心 | ✅ | ✅ | ✅（`resolve_quote_snapshot`） |

- **整理**：整理输入框内容，填入输入框，用户确认后添加；
- **扩写**：扩写选中段落或全文，自动触发备忘保存；
- **附带行情**：追加流水时前缀 `[现价 …，涨跌 …%]`。

---

## 7. AI 集成

- 看盘页：`ActionsController._note_context_extra` → `publish_quote_context` 的 `signal_extra`。
- 悬浮球：「结合笔记复盘」→ `build_note_review_prompt`。
- AI 面板：助手气泡右键存笔记（`save_from_ai.py`）。

---

## 8. 测试

| 路径 | 覆盖 |
|------|------|
| `tests/ashare/test_stock_notes_repository.py` | 备忘 / 流水 / 索引 |
| `tests/ashare/test_stock_analysis_reports_repository.py` | 报告 CRUD |
| `tests/ashare/test_note_service.py` | snippet、导出 |
| `tests/ashare/test_vnpy_notes_skill.py` | Skill |
| `tests/ashare/test_save_from_ai.py` | AI 对话存笔记 |
| `tests/ashare/test_note_ai_assist.py` | AI prompt / 扩写替换 / 行情行 |

---

## 参考

- [自选策略信号区](./watchlist-signals.md)
- [AI 数据路由](./ai-data-routing.md)
- [数据设计](./data-design.md)
