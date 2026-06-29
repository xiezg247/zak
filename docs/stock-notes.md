# 个股笔记

同一只票支持三种形态，存于 PG `app` schema；与持仓区 `notes` 字段**不合并**。

---

## 1. 三种形态

| 形态 | 交互 | 存储 |
|------|------|------|
| 流水 | 列表追加，`Ctrl+Enter` | `stock_note_entries` |
| 备忘 | Markdown，自动保存 | `stock_note_memos`（每票一行） |
| 分析报告 | 只读历史，可删 | `stock_analysis_reports`（含团队分析 `team_analysis`） |

---

## 2. 入口

| 入口 | 说明 |
|------|------|
| 自选右侧笔记面板 | 备忘 + 流水 |
| `Ctrl+Shift+N` 笔记中心 | 标的列表 + 备忘/流水/报告/计划 Tab |
| AI 气泡右键 | 存报告、追加流水 |
| `/team` 研报 | 落库后 `zak://team-report` 链接 |

---

## 3. AI

- 看盘上下文：`build_ai_snippet`（备忘 + 流水 + 最近报告摘要）
- 流水「AI 整理」、备忘「AI 扩写」（需 `LLM_API_KEY`）
- Skill：`get_stock_notes`、`append_stock_note_entry` 等（`vnpy-notes`）

---

## 参考

[自选页](./watchlist.md) · [智能体投研团队](./team-agent.md) · [AI 数据路由](./ai-data-routing.md)
