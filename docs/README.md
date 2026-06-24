# zak 文档

个人 A 股现货量化终端说明。代码入口：`packages/vnpy-ashare/`。

## 索引

| 文档 | 说明 |
|------|------|
| [交易体系](./trading-system.md) | 极致短线总纲；守则 Playbook（`Ctrl+1`） |
| [盘中工作流](./intraday-workflow.md) | 盘前→盘中→盘后主路径 |
| [功能索引](./feature-index.md) | 按域查阅全部已实现能力 |
| [产品说明](./product-plan.md) | 导航、快捷键、数据分工 |
| [架构说明](./architecture.md) | GUI 分层、Service、AI 编排 |
| [数据设计](./data-design.md) · [数据流](./data-flow.md) | 存储与触发 |
| [情绪周期](./emotion-cycle.md) · [策略 Profile](./strategy-profiles.md) | 择时与买卖点配置 |
| [市场页](./market-page.md) · [雷达页](./radar-page.md) · [雷达选龙头](./radar-leader-screening.md) | 看盘与选股 |
| [选股 Hub](./screener-hub-guide.md) · [盘中选股](./intraday-screening.md) | 条件选股与多因子 |
| [自选页](./watchlist.md) · [风控](./risk-gate.md) · [交易计划](./trading-plan-journal.md) | 仓位与纪律 |
| [策略回测](./backtest-ux.md) · [个股笔记](./stock-notes.md) | 回测与复盘 |
| [AI 数据路由](./ai-data-routing.md) · [AI 与 K 线](./ai-kline-data.md) · [团队分析](./team-agent.md) | AI 与 Skill |
| [消息通知](./notifications.md) · [信息流](./info-feed.md) | 飞书与 B 站订阅 |
| [配置热加载](./config-hot-reload.md) | instant / soft / restart |
| [编码规范](./coding-standards.md) · [mypy](./mypy.md) | 开发约定 |

Superpowers 工作区（不提交 Git）：[`superpowers/README.md`](./superpowers/README.md)

## 短线主线（推荐阅读顺序）

[Playbook](./trading-system.md#13-守则-playbook默认首屏) → [交易体系](./trading-system.md) → [盘中工作流](./intraday-workflow.md) → [情绪周期](./emotion-cycle.md) → [策略 Profile](./strategy-profiles.md) → [雷达](./radar-page.md) / [选龙头](./radar-leader-screening.md) → [自选页](./watchlist.md) → [风控](./risk-gate.md) / [交易计划](./trading-plan-journal.md)
