# 交易体系说明

> 个人 A 股现货**投研 + 规则辅助**终端：短线为主、中线为辅。**不提供**实盘下单。  
> [产品说明](./product-plan.md) · [盘中工作流](./intraday-workflow.md) · [功能索引](./feature-index.md)

---

## 1. 定位与守则

| 层级 | 周期 | 侧重 |
|------|------|------|
| 极致短线（主） | 1–3 日 | 择时、人气选股、买卖点、隔日卖、仓位系数 |
| 短线波段（辅） | 3–10 日 | 雷达展望、突破、持仓跟踪 |
| 中线观察（辅） | 2–8 周 | 团队分析、回测 |

七大模块：**择时 → 选股 → 买卖 → 仓位 → 风控 → 复盘 → 纪律**（`SIGNAL_DISCLAIMER`）。

### 1.3 守则 Playbook（默认首屏）

**Ctrl+1**：规则 Markdown + 对照条（情绪/风控/日盈亏/计划/持仓/纪律）+ checklist。§1–§5 **只读**（正文由 `config/playbook_templates/` 维护，随 Strategy Profile 切换刷新）；§2/§4 底部镜像 Profile/风控。每日 checklist 仍可按用户勾选。`ui/home/`、`trading_playbook.py`。

---

## 2. 择时

五阶段情绪周期 → 总仓位与选股 gate。详见 [情绪周期](./emotion-cycle.md)、[市场页](./market-page.md)。

---

## 3. 选股

人气股：涨停榜/连板/龙头（10cm）、题材核心（20cm）。雷达与 Recipe 见 [雷达选龙头](./radar-leader-screening.md)、[盘中选股](./intraday-screening.md)。可入自选、信号区（≤10）、下载日 K、AI 次日计划草案。

---

## 4. 策略与买卖点

打板 / 半路 / 低吸 / 隔日卖 → `AshareLimitBoard*`、`IntradayBreakout*`、`Pullback*`、`OvernightExit*`。默认 Profile `short_swing`；极致短线 `ultra_short`。映射见 [策略配置方案](./strategy-profiles.md)。

---

## 5. 仓位与风控

手工记账；仓位随情绪系数；盈利才加仓。详见 [自选页](./watchlist.md)、[风控体系](./risk-gate.md)。参考：单笔亏 ≤2%、单日 ≤3%、日内 −5%；计划 3–5、信号 ≤10、自选 ≤50。

---

## 6. 复盘、计划与 AI

笔记 + Playbook → `trading_plans`（[交易计划](./trading-plan-journal.md)、[个股笔记](./stock-notes.md)）。AI 不编造价格；工具见 [AI 数据路由](./ai-data-routing.md)。A 股 T+1、整手回测 `AShareTemplate`。

---

[情绪周期](./emotion-cycle.md) · [雷达](./radar-page.md) · [选股](./intraday-screening.md) · [通知](./notifications.md)
