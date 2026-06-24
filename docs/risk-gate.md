# 交易辅助与风控提示

> zak **不下单**。风控 = 情绪择时 + 交易参数 + 持仓异动 + 计划内校验。

---

## 1. 能力一览

| 能力 | 模块 |
|------|------|
| 择时闸（五阶段 → 建议仓位） | `quotes/market/emotion_cycle` |
| 交易参数（总资金、止损%、浮亏警戒） | `config/preferences/trading_risk.py` |
| 持仓指标（浮盈%、情绪建议文案） | `trading/risk/metrics.py` |
| 持仓异动（浮亏、卖出信号、开盘止损） | `quotes/misc/position_anomaly` |
| 计划内校验 | `trading/plans/` |

### 须识别并警告的行为

逆势抄底（退潮买入）、扛单、亏损补仓、计划外买票。

---

## 2. 交易参数 TradingRiskPrefs

QSettings `trading/risk/`：`total_capital`、`stop_loss_pct`（默认 5%）、`caution_float_pct`（默认 −5%）、`realized_pnl_today`（可选）。

---

## 3. 持仓区展示

情绪建议仓位 vs 实际记账仓位；平均浮盈 %。无账户熔断状态机。

---

## 4. 与情绪周期

| 模块 | 职责 |
|------|------|
| [情绪周期](./emotion-cycle.md) | 市场环境、退潮不做 |
| 交易参数 | 账户参考阈值 |

---

## 5. 通知事件

| event_id | 默认 |
|----------|------|
| `emotion_stage_change` | 开 |
| `position_alert` | 关 |

详见 [消息通知](./notifications.md)。

---

## 6. AI 工具

| 工具 | 说明 |
|------|------|
| `get_trading_plan` | 读 active 计划 |
| `propose_trading_plan` | 生成次日计划草案 |
| `evaluate_overnight_exit` | 隔日卖点检查 |

择时走 `get_emotion_cycle`；持仓上下文走 `build_positions_ai_prompt`。

---

## 参考

- [交易体系 §6](./trading-system.md)
- [盘中工作流](./intraday-workflow.md)
- [交易计划](./trading-plan-journal.md)
