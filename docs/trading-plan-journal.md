# 交易计划

> **纪律**：只做计划内交易；计划外登记时 toast 提示。复盘以 [笔记流水](./stock-notes.md) + Playbook 为主。

---

## 1. 双轨

| 轨道 | 存储 | 用途 |
|------|------|------|
| 笔记流水 | `stock_note_entries` | 盘中/盘后定性记录 |
| 次日计划 | `trading_plans` | 盘前 3–5 只 + 仓位 + 条件 |

---

## 2. TradingPlan 结构

```text
TradingPlan
├── trade_date, emotion_expected, max_position_pct
├── watchlist[]（3–5 只）
├── per_symbol: allowed_modes, entry/exit_conditions
└── status: draft | active | archived
```

表：`trading_plans` + `trading_plan_symbols`（`zak.db`）。

---

## 3. 工作流

```text
盘后 AI / 手动 → propose_trading_plan → 确认 → 写入 + 同步自选
盘前打开计划 / 自选上下文条 → 盘中监控 plan 内标的
登记持仓 → 校验 vt_symbol ∈ plan → 否则计划外提示
```

---

## 4. UI 入口

| 入口 | 说明 |
|------|------|
| 雷达「生成次日计划」 | AI 草稿 → 确认 |
| 自选持仓「今日计划」 | 编辑/激活 |
| 笔记中心 Tab「计划」 | 历史列表 |

---

## 5. 日复盘（约 30 分钟）

1. 市场：涨跌停、情绪阶段  
2. 计划执行：计划内/外笔数  
3. 单笔：笔记记录理由与盈亏  
4. 次日：更新信号区与 `propose_trading_plan`

---

## 6. AI 工具

| 工具 | 说明 |
|------|------|
| `propose_trading_plan` | 雷达/情绪上下文 → 草案 |
| `get_trading_plan` | 读当日 active plan |
| `evaluate_overnight_exit` | 隔日卖点检查 |

---

## 参考

- [交易体系 §7](./trading-system.md)
- [个股笔记](./stock-notes.md)
- [风控体系](./risk-gate.md)
