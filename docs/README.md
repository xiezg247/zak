# zak 文档

个人 A 股现货量化终端的设计与操作说明。入口代码：`packages/vnpy-ashare/`。

## 产品与架构

| 文档 | 说明 |
|------|------|
| [产品说明](./product-plan.md) | 功能模块、导航、数据分工 |
| [架构说明](./architecture.md) | GUI 分层、Service、行情 Provider、AI 编排 |
| [数据设计](./data-design.md) | 双存储（SQLite 元数据 + SQLite/PostgreSQL K 线）+ Redis + context_store |

## 功能域

| 文档 | 说明 |
|------|------|
| [策略回测](./backtest-ux.md) | 联动、批量回测、摘要落库 |
| [自选策略信号区](./watchlist-signals.md) | 独立信号面板、缓存、联动与限额 |
| [自选多维看盘](./watchlist-multiview.md) | 表格/多维切换、卡片网格、迷你图与 AI 摘要 |
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
