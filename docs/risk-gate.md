# 交易辅助与风控提示

zak **不下单**。风控 = 情绪择时 + 交易参数 + 持仓异动 + 计划内校验。

| 能力 | 模块 |
|------|------|
| 五阶段 → 建议仓位 | `emotion_cycle`（见 [情绪周期](./emotion-cycle.md)） |
| 总资金、止损%、浮亏警戒 | `trading_risk.py`（QSettings `trading/risk/`） |
| 浮盈%、建议仓位文案 | `trading/risk/metrics.py` |
| 异动（浮亏、卖出信号、开盘止损） | `position_anomaly` |
| 计划内校验 | `trading/plans/` |

**须警告**：退潮买入、扛单、亏损补仓、计划外买票。

持仓区展示情绪建议仓位 vs 实际记账仓位；无账户熔断状态机。通知：`emotion_stage_change`（默认开）、`position_alert`（默认关），见 [消息通知](./notifications.md)。

AI：`get_trading_plan`、`propose_trading_plan`、`evaluate_overnight_exit`；择时走 `get_emotion_cycle`；持仓上下文 `build_positions_ai_prompt`。

---

[交易体系 §5](./trading-system.md#5-仓位与风控) · [盘中工作流](./intraday-workflow.md) · [交易计划](./trading-plan-journal.md)
