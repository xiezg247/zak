# 交易体系说明

> 个人 A 股现货**投研 + 规则辅助**终端：短线为主、中线为辅。**不提供**实盘下单。  
> 导航见 [产品说明](./product-plan.md)；日路径见 [盘中工作流](./intraday-workflow.md)。

---

## 1. 定位与守则

| 层级 | 周期 | 侧重 |
|------|------|------|
| 极致短线（主） | 1–3 日 | 择时、人气选股、买卖点、隔日卖、仓位系数 |
| 短线波段（辅） | 3–10 日 | 雷达展望、突破策略、持仓跟踪 |
| 中线观察（辅） | 2–8 周 | 团队分析、回测验证 |

七大模块：**择时 → 选股 → 买卖 → 仓位 → 风控 → 复盘 → 纪律**。系统输出规则参考与环境提示，不构成买卖建议（`SIGNAL_DISCLAIMER`）。

### 1.3 守则 Playbook（默认首屏）

侧栏 **Ctrl+1**：规则 Markdown + 今日对照条 + 纪律 checklist。

| 区块 | 内容 |
|------|------|
| 对照条 | 情绪 / 风控 / 日盈亏 / 今日计划 / 持仓 / 纪律进度 |
| §1–§5 | 择时、选股、买卖、仓位风控、纪律（用户 Markdown + Profile/风控只读镜像） |

实现：`ui/home/`、`services/trading_playbook.py`。

---

## 2. 择时

五阶段情绪周期驱动总仓位与选股 gate（冰点→退潮）。辅助：成交额、大盘 5 日线、监管异动、恐贪（`sentiment_gate`）。

落点：市场页广度、顶栏 `EmotionCycleChip`、选股 `emotion_gate`、退潮入自选提示。详见 [情绪周期](./emotion-cycle.md)、[市场页](./market-page.md)。

---

## 3. 选股

只做市场资金选出的票：涨停榜/连板/龙头（10cm）、题材核心（20cm）。硬过滤三模板；雷达连板、龙头评分、共振见 [雷达选龙头](./radar-leader-screening.md)。

常用 Recipe：`ultra_short_limit`、`ultra_short_first_board`、`cm20_elastic`、`emotion_gate_only`、`ultra_short_unified`、`intraday_multi`。细节见 [盘中选股](./intraday-screening.md)。

结果可：入自选、入信号区（≤10）、下载日 K、AI 次日计划草案。

---

## 4. 策略与买卖点

| 模式 | 策略插件 |
|------|----------|
| 打板 | `AshareLimitBoardStrategy` |
| 半路 | `AshareIntradayBreakoutStrategy` |
| 低吸 | `AsharePullbackStrategy` |
| 隔日卖 | `AshareOvernightExitStrategy`（持仓 overlay） |

信号区默认 `short_swing`（`AshareShortBreakoutStrategy`）；极致短线 Profile `ultra_short`。分 K 有 `*MinuteStrategy`。

隔日卖点规则：冲高滞涨止盈、核按钮/低开止损、日内 −5%、破开盘价等；持仓区 `exit_rules` 列展示。Profile 映射见 [策略配置方案](./strategy-profiles.md)。

---

## 5. 仓位与风控

手工记账；单票/总仓随情绪系数，永不满仓；盈利才加仓。持仓区 header：Profile、建议 vs 实际仓位、登记与筛选。见 [自选页](./watchlist.md)。

| 风控 | 落点 |
|------|------|
| 交易参数 | 总资金、止损 %、浮亏警戒 |
| 异动 | toast / 飞书（默认关） |
| 计划外 | 登记时 toast |
| 铁则 | 退潮买入、扛单、亏损补仓、计划外买票须警告 |

Playbook 对照单笔/单日/周期回撤。详见 [风控体系](./risk-gate.md)。

**默认参考**：单笔亏 ≤2% 总资金、单日 ≤3%、日内止损 −5%；计划 3–5 只、信号 ≤10、自选 ≤50。

---

## 6. 复盘与计划

市场复盘（市场页 + 情绪）→ 交易复盘（笔记 + Playbook）→ 次日计划 `trading_plans`（3–5 只 + 仓位 + 条件）。`propose_trading_plan` 草案须确认写入。见 [交易计划](./trading-plan-journal.md)、[个股笔记](./stock-notes.md)。

---

## 7. AI 与数据

AI 不编造价格；常用：`get_emotion_cycle`、`run_leader_screen`、`propose_trading_plan`、`evaluate_entry_mode`、`evaluate_overnight_exit`。见 [AI 数据路由](./ai-data-routing.md)、[团队分析](./team-agent.md)。数据触发见 [数据流](./data-flow.md)。

A 股：T+1、10cm/20cm、异动监管提示、整手回测（`AShareTemplate`）。个人投研终端，持仓为手工记账。

---

## 相关文档

[盘中工作流](./intraday-workflow.md) · [功能索引](./feature-index.md) · [情绪周期](./emotion-cycle.md) · [雷达](./radar-page.md) · [选股](./intraday-screening.md) · [自选](./watchlist.md) · [风控](./risk-gate.md) · [通知](./notifications.md)
