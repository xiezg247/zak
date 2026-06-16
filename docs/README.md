# zak 文档

| 文档 | 说明 |
|------|------|
| [产品说明](./product-plan.md) | 功能、导航、数据分工 |
| [架构说明](./architecture.md) | GUI 分层、Service、行情 Provider、AI |
| [数据设计](./data-design.md) | 双存储（SQLite 元数据 + SQLite/PostgreSQL K线）+ Redis + context_store |
| [策略回测](./backtest-ux.md) | 联动、批量回测、摘要落库 |
| [自选策略信号区](./watchlist-signals.md) | 独立信号面板、缓存、联动与限额 |
| [自选多维看盘](./watchlist-multiview.md) | 表格/多维切换、卡片网格、迷你图与 AI 摘要 |
| [看盘页个股笔记](./stock-notes.md) | 备忘 + 流水双形态、NoteService、AI 上下文 |
| [AI 数据路由](./ai-data-routing.md) | Skill / MCP 与数据源 |
| [AI 功能与 K 线](./ai-kline-data.md) | 各功能域对本地日 K 的依赖与下载建议 |
| [盘中选股](./intraday-screening.md) | Recipe 多因子维度、硬过滤、AI 工具与结果洞察 |
| [配置分级热加载](./config-hot-reload.md) | 配置页保存后的 instant / soft / restart 策略 |
| [编码规范](./coding-standards.md) | 代码风格、注释、分层约定 |
| [mypy 静态类型检查](./mypy.md) | 各 package 配置与本地检查入口 |
