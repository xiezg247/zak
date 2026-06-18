# 风控体系

> **原则**：活下去是第一目标。zak **不下单**，风控表达为 **提示、软拦截、熔断状态** + 登记辅助计算。阈值来自 [交易体系 §6](./trading-system.md#六风控体系活下去是第一目标) 与附录 B。

---

## 1. 三层风控

| 层级 | 阈值（默认） | 系统动作 |
|------|--------------|----------|
| **单笔** | 亏损 ≤ 总资金 **2%** | 登记持仓时：成本 + 止损% → 建议最大股数 |
| **单日** | 当日亏损 ≤ 总资金 **3%** | 状态 `caution`；禁止新开仓提示 |
| **周期** | 单周回撤 **5%** → 空仓 2 天；总回撤 **10%** → 停手 1 周 | 状态 `halt`；强制复盘入口 |

### 1.1 绝对禁止（须识别并警告）

| 行为 | 检测方式 |
|------|----------|
| 逆势抄底 | `emotion_cycle` 退潮/冰点 + 新开持仓 |
| 扛单死等 | 浮亏 ≤ −5% 且无卖出动作（流水无 sell 记录） |
| 亏损补仓 | 同标的二次登记且成本下调（**已有**，`add_loss` 标签） |
| 计划外买票 | 不在 TradingPlan.watchlist（**已有**，`off_plan` 标签） |

---

## 2. 风控闸状态机

```text
                    ┌──────────┐
         正常交易    │  normal  │
                    └────┬─────┘
                         │ 单日亏 ≥3% 或 周回撤 ≥5%
                         ▼
                    ┌──────────┐
                    │ caution  │  减频、确认框、AI 风险提示
                    └────┬─────┘
                         │ 总回撤 ≥10% 或 连续 caution N 日
                         ▼
                    ┌──────────┐
                    │   halt   │  禁止新开；仅允许卖/复盘
                    └──────────┘
```

### 2.1 RiskGateSnapshot

```python
# domain/trading/risk.py

class RiskGateSnapshot(FrozenModel):
    state: RiskGateState            # normal | caution | halt
    state_label: str
    allow_new_positions: bool
    daily_pnl_pct: float | None     # 当日盈亏占比（%）
    avg_float_pnl_pct: float | None
    weekly_drawdown_pct: float | None
    total_drawdown_pct: float | None
    halt_until: str | None
    warnings: tuple[str, ...]
```

模块路径：`packages/vnpy-ashare/vnpy_ashare/domain/trading/risk.py`（计算逻辑在 `trading/risk/`）  
配置 QSettings：`trading/risk/total_capital`、`trading/risk/*_threshold`。

---

## 3. 单笔风险计算器

**场景**：登记持仓前，用户输入成本价、计划止损比例（默认 5% 或 Profile 指定）。

```text
max_loss_amount = total_capital × 2%
max_shares = floor(max_loss_amount / (cost × stop_loss_pct) / 100) × 100
```

| 输入 | 来源 |
|------|------|
| `total_capital` | 用户设置（默认空 → 仅比例提示） |
| `cost_price` | 登记对话框 |
| `stop_loss_pct` | Profile 默认 5%；极致短线 −5% 铁则 |

UI：`PositionEditDialog` 底部展示「按 2% 风控建议 ≤ N 股」。

---

## 4. 盈亏汇总

| 组成 | 计算 |
|------|------|
| 浮盈 | Σ 持仓 `unrealized_pnl` |
| 已实现 | Σ `trade_journal.realized_pnl`（**已有**） |
| 当日合计 | 已实现（当日） + 浮盈变动（可选近似：当前浮盈 − 昨收快照） |

**Phase 1 简化**：仅浮亏 + 手动标记「今日已实现」；Phase 2 接 trade_journal。

---

## 5. Gate 接入点

| 消费者 | normal | caution | halt |
|--------|--------|---------|------|
| 登记持仓 | 允许 | 二次确认 | 警告，不阻断记账 |
| 选股批量入自选 | 允许 | 确认 | 软拦截 |
| 雷达/龙头选股 | 允许 | 降 top_n | 空结果 |
| emotion 退潮 | 叠加：禁止新开 | 同左 | 同左 |
| AI `check_risk_gate` | 返回状态 JSON | 须提示 | 默认不建议操作 |

---

## 6. UI

| 位置 | 组件 |
|------|------|
| 自选页持仓区 header | 风控芯片：正常 / 谨慎 / 熔断 |
| 设置 → 交易风控 | 总资金、阈值、重置峰值 |
| 熔断时 | 笔记中心弹出「强制复盘」链接 |
| 出站 | `risk_gate_change` → 飞书（见 [消息通知](./notifications.md)） |

---

## 7. AI 与 Skill

| 工具 | 说明 |
|------|------|
| `check_risk_gate` | 返回 RiskGateSnapshot |
| `compute_position_size` | 单笔 2% 计算器 ✅ |

Prompt：halt/caution 时必须引用具体回撤数字，禁止编造。

---

## 8. 与情绪周期关系

| 模块 | 职责 |
|------|------|
| [emotion-cycle](./emotion-cycle.md) | **市场环境**：退潮不做 |
| **risk-gate** | **账户状态**：亏了太多不做 |

两者同时 `allow_new_positions=false` 时，UI 合并展示「环境退潮 + 账户熔断」。自选 / 雷达顶栏 **`EmotionCycleChip` + `RiskGateChip`**（点击风控芯片打开设置）。

---

## 9. 实施分期

| Phase | 交付 |
|-------|------|
| 1 | 总资金设置 + 单笔计算器 + 浮亏 −5% 已有异动联动 |
| 2 | 状态机 + 选股/登记软拦截 |
| 3 | trade_journal 已实现盈亏 + 周/总回撤自动熔断 |

---

## 10. 测试

| 用例 | 断言 |
|------|------|
| 2% 计算 | 10 万资金、成本 10、止损 5% → 4000 股 |
| halt | `allow_new_positions is False` |
| 退潮 + halt | 双重 warning |

---

## 参考

- [交易体系 §6](./trading-system.md)
- [盘中工作流 §3.2](./intraday-workflow.md)
- [交易计划与流水](./trading-plan-journal.md)
