# 交易体系说明

> 个人 A 股现货**投研 + 规则辅助**终端：短线为主、中线为辅。**不提供**实盘下单。  
> 导航与模块见 [产品说明](./product-plan.md)；日路径见 [盘中工作流](./intraday-workflow.md)。

---

## 1. 产品定位

### 1.1 交易风格分层

| 层级 | 持股周期 | 在 zak 中的侧重 |
|------|----------|-----------------|
| **极致短线（主）** | 1–3 日 | 择时、人气选股、买卖点规则、隔日卖点、仓位系数 |
| **短线波段（辅）** | 3–10 日 | 雷达展望、突破策略、持仓跟踪 |
| **中线观察（辅）** | 2–8 周 | 团队分析、回测验证 |

**设计原则**：系统输出规则参考与环境提示，不构成买卖建议（`SIGNAL_DISCLAIMER`）。

### 1.2 七大模块

```text
择时 → 选股 → 买卖 → 仓位 → 风控 → 复盘 → 纪律
```

对应：市场环境/情绪周期、选股 Hub/雷达、策略信号/分 K、持仓区、交易参数/异动、笔记/计划、守则 Playbook。

### 1.3 守则 Playbook（默认首屏）

侧栏 **Ctrl+1 · 守则**：规则 Markdown + 今日对照条 + 纪律 checklist。

| 区块 | 内容 |
|------|------|
| 对照条 | 情绪 / 风控 / 日盈亏 / 今日计划 / 持仓 / 纪律进度 |
| §1–§5 | 择时、选股、买卖、仓位风控、纪律（用户 Markdown + Profile/风控只读镜像） |

三层：模板 seed → 用户编辑持久化 → §2/§4 底部只读镜像。  
实现：`ui/home/`、`services/trading_playbook.py`。

---

## 2. 择时：情绪周期

| 阶段 | 策略倾向 | 建议总仓位 |
|------|----------|------------|
| 冰点 | 空仓或 ≤1 成试错 | 0%–10% |
| 启动 | 首板/二板试错 | 30%–50% |
| 发酵/高潮 | 龙头/前排 | 60%–80% |
| 分歧 | 减仓，核心低吸 | ≤30% |
| 退潮 | 不新开仓 | 0% |

辅助：两市成交额、大盘 5 日线、监管异动、恐贪指数（`sentiment_gate`）。

| 能力 | 落点 |
|------|------|
| 市场广度、涨跌停 | 市场页 `stats_bar` |
| 情绪周期引擎 | `quotes/market/emotion_cycle.py` |
| 顶栏芯片 | 市场/自选/雷达 `EmotionCycleChip` |
| 选股 gate | `screener/sentiment/emotion_gate` |
| 退潮批量入自选提示 | 选股结果操作条 |

详见 [情绪周期引擎](./emotion-cycle.md)。

---

## 3. 选股：人气股

**原则**：只做市场资金选出来的票。

| 池 | 来源 | 市值/流动性（参考） |
|----|------|---------------------|
| 10cm 主板 | 涨停榜、连板梯队、龙头 | 30–200 亿；日成交额 ≥5000 万 |
| 20cm | 涨幅 ≥10% 题材、趋势核心 | 20–150 亿；半路/低吸为主 |

| Recipe | 用途 |
|--------|------|
| `ultra_short_limit` | 极致短线主池 |
| `ultra_short_first_board` | 启动期首板 |
| `cm20_elastic` | 20cm 弹性 |
| `emotion_gate_only` | 退潮观察 |
| `ultra_short_unified` | 雷达统一选股 |
| `intraday_multi` | 默认盘中多因子 |

硬过滤三模板（保守/均衡/激进）；雷达连板梯队、龙头评分、共振入自选见 [雷达选龙头](./radar-leader-screening.md)。

选股结果可：入自选、入信号区（≤10）、下载日 K、AI 生成次日计划草案。

---

## 4. 策略与买卖点

### 4.1 三类买点

| 模式 | 规则要点 | 策略插件 |
|------|----------|----------|
| 打板 | 涨停触及、封板回封、≤10:30 | `AshareLimitBoardStrategy` |
| 半路 | 涨幅 3–7%、带量突破 | `AshareIntradayBreakoutStrategy` |
| 低吸 | MA5 或 −3%~−5% 承接 | `AsharePullbackStrategy` |
| 隔日卖 | 持仓 overlay | `AshareOvernightExitStrategy` |

信号区默认 `short_swing`（`AshareShortBreakoutStrategy`）；极致短线切 Profile `ultra_short`。分 K 有对应 `*MinuteStrategy` 与参考线。

### 4.2 隔日卖点（规则引擎）

开盘冲高滞涨止盈、核按钮/低开止损、日内 −5%、跌破开盘价等；持仓区 `exit_rules` 列展示触发状态。

### 4.3 Profile

| Profile | 信号 | 退出 |
|---------|------|------|
| 极致短线 | LimitBoard + Pullback | OvernightExit |
| 短线波段 | ShortBreakout | 策略内 |
| 中线观察 | DoubleMA | DoubleMA |

详见 [策略配置方案](./strategy-profiles.md)。

---

## 5. 仓位

手工记账，表达计划仓位 vs 实际仓位。

| 规则 | 说明 |
|------|------|
| 单票/总仓 | 随情绪系数；永不满仓 |
| 加仓 | 仅盈利头寸；亏损不补仓 |
| 分组 Tab | 自选内视图筛选 + 分组仓位汇总 |

持仓区 header：Profile、情绪建议仓位 vs 实际、登记、筛选（待卖/T+1/浮亏）。见 [自选持仓区](./watchlist-positions.md)。

---

## 6. 风控

| 层级 | 表达 |
|------|------|
| 单笔/单日/周期回撤 | Playbook 铁则 + 用户对照 |
| 交易参数 | 总资金、止损 %、浮亏警戒（QSettings） |
| 异动 | 浮亏、卖出信号、开盘止损 → toast/飞书 |
| 计划外 | 登记时 toast |

择时由情绪周期负责；详见 [风控体系](./risk-gate.md)。

**须警告**：退潮买入、扛单、亏损补仓、计划外买票。

---

## 7. 复盘与计划

| 步骤 | 工具 |
|------|------|
| 市场复盘 | 市场页 + 情绪周期 |
| 交易复盘 | 笔记流水 + Playbook |
| 次日计划 | `trading_plans`（3–5 只 + 仓位 + 条件） |

`propose_trading_plan` AI 草案 → 用户确认写入。见 [交易计划](./trading-plan-journal.md)、[个股笔记](./stock-notes.md)。

---

## 8. A 股适配

T+1 锁定、10cm/20cm 区分、异动监管提示、整手回测（`AShareTemplate`）。

---

## 9. AI

不编造价格；走 Skill / MCP。常用工具：`get_emotion_cycle`、`run_leader_screen`、`propose_trading_plan`、`evaluate_entry_mode`、`evaluate_overnight_exit`。  
路由见 [AI 数据路由](./ai-data-routing.md)；团队分析见 [team-agent](./team-agent.md)。

---

## 10. 数据流（简图）

```text
行情 Job / Redis → market_breadth / limit_list / sector_flow
                        ↓
                 emotion_cycle → screener gate
                        ↓
              radar / context_store ← notes / plans
                        ↓
                 AI / 信号区 / 持仓区 → position_anomaly → 通知
```

---

## 11. 合规

个人投研终端；信号为规则计算结果；持仓为手工记账；不得暗示收益承诺。

---

## 相关文档

[盘中工作流](./intraday-workflow.md) · [功能索引](./implementation-roadmap.md) · [产品说明](./product-plan.md) · [情绪周期](./emotion-cycle.md) · [雷达](./radar-page.md) · [选股](./intraday-screening.md) · [自选](./watchlist-ui.md) · [风控](./risk-gate.md) · [通知](./notifications.md)

### 附录：默认参数

| 参数 | 值 |
|------|-----|
| 单笔最大亏损 | 总资金 2% |
| 单日最大亏损 | 总资金 3% |
| 日内止损线 | −5% |
| 交易计划 | 3–5 只 |
| 信号区 | ≤10 只 |
| 自选池 | ≤50 只 |
