# 功能索引

> 按域列出 zak 已实现能力，细节见各专题文档。总纲见 [交易体系](./trading-system.md)，日路径见 [盘中工作流](./intraday-workflow.md)。

---

## 守则与纪律

| 能力 | 文档 |
|------|------|
| Playbook 首屏、对照条、纪律 checklist | [交易体系 §1.3](./trading-system.md#13-守则-playbook默认首屏) |
| 次日交易计划、计划内校验 | [交易计划](./trading-plan-journal.md) |
| 笔记流水复盘 | [看盘页个股笔记](./stock-notes.md) |

## 择时

| 能力 | 文档 |
|------|------|
| 市场广度、恐贪、北向环境 | [市场页](./market-page.md) |
| 五阶段情绪周期、仓位系数、gate | [情绪周期引擎](./emotion-cycle.md) |
| 退潮期选股软拦截 | [盘中选股](./intraday-screening.md) |

## 选股

| 能力 | 文档 |
|------|------|
| 条件选股、多因子 Recipe、硬过滤 | [选股 Hub](./screener-hub-guide.md)、[盘中选股](./intraday-screening.md) |
| 雷达十卡、共振、选龙头 | [雷达页](./radar-page.md)、[雷达选龙头](./radar-leader-screening.md) |
| 板块资金 → 雷达/选股跳转 | [市场页](./market-page.md)、[架构说明](./architecture.md) |

## 自选与仓位

| 能力 | 文档 |
|------|------|
| 自选页 UI、工作流预设 | [自选页 UI](./watchlist-ui.md) |
| 分组 Tab、信号区、持仓区、多维看盘 | [分组](./watchlist-groups.md)、[信号区](./watchlist-signals.md)、[持仓区](./watchlist-positions.md)、[多维](./watchlist-multiview.md) |
| 策略 Profile、买卖点、隔日退出 | [策略配置方案](./strategy-profiles.md) |
| 计划仓位、情绪系数对比 | [持仓区](./watchlist-positions.md) |

## 风控与通知

| 能力 | 文档 |
|------|------|
| 交易参数、持仓异动 | [风控体系](./risk-gate.md) |
| 飞书 Webhook、事件白名单 | [消息通知](./notifications.md) |

## AI 与数据

| 能力 | 文档 |
|------|------|
| Skill / MCP 路由、页面 AI 入口 | [AI 数据路由](./ai-data-routing.md) |
| 投研团队 `/team` | [智能体投研团队](./team-agent.md) |
| K 线依赖与补全建议 | [AI 功能与 K 线](./ai-kline-data.md) |
| 双存储、表结构 | [数据设计](./data-design.md) |
| B 站信息流 | [信息流](./info-feed.md) |

## 运维

| 能力 | 文档 |
|------|------|
| 回测联动、批量对比 | [策略回测](./backtest-ux.md) |
| 配置热加载 | [配置分级热加载](./config-hot-reload.md) |
| 数据流触发 | [数据流与触发方式](./data-flow.md) |
