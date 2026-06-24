# 交易辅助与风控提示

> **原则**：活下去是第一目标。zak **不下单**，风控表达为 **环境提示 + 持仓异动提醒** + 可选交易参数（总资金、止损比例）。  
> **2026-06 变更**：已移除账户风控闸状态机（normal / caution / halt）、顶栏芯片、`check_risk_gate` AI 工具及 `trade_journal` 结构化流水；择时仍由 [情绪周期](./emotion-cycle.md) 负责。

---

## 1. 当前能力

| 能力 | 说明 | 模块 |
|------|------|------|
| **择时闸** | 五阶段情绪周期 → 是否建议新开仓、建议总仓位 | `quotes/market/emotion_cycle` |
| **交易参数** | 总资金、默认止损 %、浮亏警戒 %、当日已实现（可选手动） | `config/preferences/trading_risk.py` |
| **持仓指标** | 平均浮盈 %、情绪建议仓位文案 | `trading/risk/metrics.py` |
| **持仓异动** | 浮亏 ≤ 阈值、卖出信号、开盘止损等 → toast / 可选飞书 | `quotes/misc/position_anomaly` |
| **计划内校验** | 登记持仓时对照 `trading_plans`（`off_plan` 等逻辑保留于计划模块） | `trading/plan/` |
| **浮亏扛单判定** | 浮亏超阈且无卖出动作（纯函数，供计划/Playbook） | `trading/risk/float_loss_hold.py` |

### 1.1 绝对禁止（须识别并警告）

| 行为 | 检测方式 |
|------|----------|
| 逆势抄底 | `emotion_cycle` 退潮/冰点 + 新开持仓 toast |
| 扛单死等 | 浮亏 ≤ 警戒阈值 + 持仓异动 |
| 亏损补仓 | 同标的二次登记且成本下调 |
| 计划外买票 | 不在 TradingPlan.watchlist |

---

## 2. 交易参数 TradingRiskPrefs

QSettings 前缀 `trading/risk/`：

```python
class TradingRiskPrefs(FrozenModel):
    total_capital: float | None      # 总资金（可选）
    stop_loss_pct: float              # 默认止损比例，默认 5%
    caution_float_pct: float          # 浮亏警戒，默认 −5%
    realized_pnl_today: float | None  # 当日已实现（可选手动覆盖）
```

模块：`packages/vnpy-ashare/vnpy_ashare/config/preferences/trading_risk.py`

---

## 3. 持仓区指标

| 函数 | 用途 |
|------|------|
| `read_total_capital()` | 读取总资金，供仓位 % 列 |
| `compute_avg_float_pnl_pct(cache)` | 持仓平均浮盈 % |
| `format_emotion_position_hint(min, max)` | 「情绪建议 30–50%」类文案 |

模块：`trading/risk/metrics.py`

持仓区 header 展示：**情绪建议仓位** vs **实际记账仓位**；无顶栏风控芯片、无熔断状态机。

---

## 4. 与情绪周期的关系

| 模块 | 职责 |
|------|------|
| [emotion-cycle](./emotion-cycle.md) | **市场环境**：退潮不做、建议仓位系数 |
| **交易参数** | **账户参考**：总资金、浮亏阈值、可选当日已实现 |

两者叠加时，UI 以情绪芯片 + 持仓 stats 合并展示；**不再**单独输出 caution / halt 账户闸。

---

## 5. 通知

| event_id | 说明 | 默认 |
|----------|------|------|
| `emotion_stage_change` | 情绪阶段变更 | 开 |
| `position_alert` | 持仓异动（浮亏、卖出信号等） | 关 |

已移除：`risk_gate_change`、`journal_violation`。详见 [消息通知](./notifications.md)。

---

## 6. AI 工具（vnpy-trading）

| 工具 | 状态 |
|------|------|
| `get_trading_plan` | **已有** |
| `propose_trading_plan` | **已有** |
| `evaluate_overnight_exit` | **已有** |
| ~~`check_risk_gate`~~ | **已移除** |
| ~~`compute_position_size`~~ | **已移除** |
| ~~`get_trade_journal`~~ | **已移除** |

择时问题应走 `get_emotion_cycle`；持仓问题走 `build_positions_ai_prompt` / `evaluate_overnight_exit`。

---

## 7. 已归档能力（不再实现）

以下曾在 Phase 3 交付，已于 2026-06 移除：

- 风控闸状态机（normal / caution / halt）与 `RiskGateEngine`
- 顶栏 `RiskGateChip`、持仓区「风控设置」高级页（回撤熔断、手动停手等）
- 单笔 2% 计算器 AI 工具与登记对话框联动
- `trade_journal` 表及登记买入/卖出流水、复盘流水明细 CRUD
- 飞书 `risk_gate_change` / `journal_violation` 事件

---

## 参考

- [交易体系 §6](./trading-system.md#六风控体系活下去是第一目标)
- [盘中工作流 §3.2](./intraday-workflow.md)
- [交易计划](./trading-plan-journal.md)
- [情绪周期引擎](./emotion-cycle.md)
