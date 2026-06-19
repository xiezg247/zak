# zak 文档

个人 A 股现货量化终端的设计与操作说明。入口代码：`packages/vnpy-ashare/`。

## 产品与架构

| 文档 | 说明 |
|------|------|
| [产品说明](./product-plan.md) | 功能模块、导航、数据分工 |
| [交易体系需求](./trading-system.md) | 极致短线为主：择时 / 选股 / 买卖 / 仓位 / 风控 / 复盘 / AI 总纲 |
| [实施路线图](./implementation-roadmap.md) | 需求 ID 总表（T-/R-/G-/K-/J-/N-/A-）状态与分期 |
| [盘中工作流](./intraday-workflow.md) | 盘前→盘中→盘后短线主路径 |
| [情绪周期引擎](./emotion-cycle.md) | 五阶段择时、仓位系数、gate |
| [策略配置方案](./strategy-profiles.md) | 现有四套策略去留、Profile 映射 |
| [架构说明](./architecture.md) | GUI 分层、Service、行情 Provider、AI 编排 |
| [数据设计](./data-design.md) | 双存储（SQLite 元数据 + SQLite/PostgreSQL K 线）+ Redis + context_store |
| [数据流与触发方式](./data-flow.md) | 冷启动 / 打开页 / 定时 / 手动四档数据流 |

## 功能域

| 文档 | 说明 |
|------|------|
| [策略回测](./backtest-ux.md) | 联动、批量回测、摘要落库 |
| [自选策略信号区](./watchlist-signals.md) | 独立信号面板、缓存、联动与限额 |
| [自选分组](./watchlist-groups.md) | Tab 分组、与自选池/信号区关系 |
| [自选持仓区](./watchlist-positions.md) | 记账、T+1、退出信号、异动 |
| [自选多维看盘](./watchlist-multiview.md) | 表格/多维切换、卡片网格、迷你图与 AI 摘要 |
| [雷达选龙头](./radar-leader-screening.md) | 连板梯队、龙头评分、龙头选股 |
| [雷达页](./radar-page.md) | 十卡布局、共振、与 Hub/板块分工 |
| [市场页](./market-page.md) | 广度、排行、涨停池与择时输入 |
| [风控体系](./risk-gate.md) | 三层风控、状态机、单笔计算器 |
| [交易计划与流水](./trading-plan-journal.md) | 次日计划、trade_journal、纪律标记 |
| [消息通知（飞书）](./notifications.md) | Webhook、事件白名单、与定时任务/风控联动 |
| [看盘页个股笔记](./stock-notes.md) | 备忘 + 流水双形态、NoteService、AI 上下文 |
| [盘中选股](./intraday-screening.md) | Recipe 多因子维度、硬过滤、AI 工具与结果洞察 |
| [选股 Hub 使用指南](./screener-hub-guide.md) | 条件选股 / 多因子配方操作速查 |
| [配置分级热加载](./config-hot-reload.md) | 配置页保存后的 instant / soft / restart 策略 |

## AI

| 文档 | 说明 |
|------|------|
| [AI 数据路由](./ai-data-routing.md) | Skill / MCP 与数据源、意图路由总表 |
| [AI 功能与 K 线](./ai-kline-data.md) | 各功能域对本地日 K 的依赖与下载建议 |
| [智能体投研团队](./team-agent.md) | 并行财务/风险/策略分析 + chief 汇总（`/team` 命令） |
| [Skill 目录](../skills/README.md) | 各 Skill 的 `SKILL.md` 与 Python 实现（详见 [AI 数据路由 §Skill](./ai-data-routing.md#skill-源码与-skillmd)） |

## 开发

| 文档 | 说明 |
|------|------|
| [编码规范](./coding-standards.md) | 分层约定、类型注解、K 线访问门面 |
| [mypy 静态类型检查](./mypy.md) | 各 package 配置与本地检查入口 |

> **Superpowers 工作区**（设计 spec / 实现 plan，**不提交 Git**）：[`docs/superpowers/README.md`](./superpowers/README.md)

## 短线主线阅读顺序

1. [交易体系需求](./trading-system.md) — 总纲与分期  
2. [实施路线图](./implementation-roadmap.md) — ID 状态一览  
3. [盘中工作流](./intraday-workflow.md) — 日路径  
4. [情绪周期引擎](./emotion-cycle.md) — 择时 blocker  
5. [策略配置方案](./strategy-profiles.md) — 策略去留与 Profile  
6. [雷达页](./radar-page.md) / [雷达选龙头](./radar-leader-screening.md) — 选股主池  
7. [自选分组](./watchlist-groups.md) / [持仓区](./watchlist-positions.md) / [信号区](./watchlist-signals.md) — 自选页三件套  
8. [风控体系](./risk-gate.md) / [交易计划与流水](./trading-plan-journal.md) — 纪律闭环  
9. [消息通知（飞书）](./notifications.md) — 盘外提醒  
