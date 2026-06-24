# 交易计划

**纪律**：只做计划内交易；计划外登记 toast。复盘以 [笔记流水](./stock-notes.md) + Playbook 为主。

| 轨道 | 存储 | 用途 |
|------|------|------|
| 笔记流水 | `stock_note_entries` | 定性记录 |
| 次日计划 | `trading_plans` + `trading_plan_symbols` | 3–5 只 + 仓位 + 条件 |

字段：`trade_date`、`emotion_expected`、`max_position_pct`、每只 `allowed_modes` / 进出场条件；状态 `draft | active | archived`。

```text
盘后 propose_trading_plan → 确认写入
盘前打开计划 → 盘中监控 plan 内标的
登记持仓 → 校验 ∈ plan，否则计划外提示
```

入口：雷达「生成次日计划」、自选「今日计划」、笔记中心「计划」Tab。

AI：`propose_trading_plan`、`get_trading_plan`、`evaluate_overnight_exit`。

---

[交易体系 §6](./trading-system.md#6-复盘与计划) · [风控](./risk-gate.md)
