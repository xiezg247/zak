# zak 文档

| 文档 | 说明 |
|------|------|
| [产品说明](./product-plan.md) | 功能、导航、数据分工 |
| [架构说明](./architecture.md) | GUI 分层、Service、行情 Provider、AI |
| [数据设计](./data-design.md) | 双存储（SQLite 元数据 + SQLite/PostgreSQL K线）+ Redis + context_store |
| [策略回测](./backtest-ux.md) | 联动、批量回测、摘要落库 |
| [自选策略信号区](./watchlist-signals-design.md) | 独立信号面板、缓存、联动与限额 |
| [AI 数据路由](./ai-data-routing.md) | Skill / MCP 与数据源 |
| [AI 功能与 K 线](./ai-kline-data.md) | 各功能域对本地日 K 的依赖与下载建议 |
| [编码规范](./coding-standards.md) | 代码风格、注释、分层约定 |
