# zak 文档

| 文档 | 说明 |
|------|------|
| [产品说明](./product-plan.md) | 功能、导航、数据分工 |
| [架构说明](./architecture.md) | GUI 分层、Service、行情 Provider、AI |
| [数据设计](./data-design.md) | 双存储（SQLite 元数据 + SQLite/PostgreSQL K线）+ Redis + context_store |
| [策略回测](./backtest-ux.md) | 联动、批量回测、摘要落库 |
| [自选策略信号区](./watchlist-signals-design.md) | 独立信号面板、缓存、联动与限额 |
| [看盘页个股笔记](./stock-notes-design.md) | 备忘 + 流水双形态、NoteService、AI 上下文 |
| [AI 数据路由](./ai-data-routing.md) | Skill / MCP 与数据源 |
| [AI 功能与 K 线](./ai-kline-data.md) | 各功能域对本地日 K 的依赖与下载建议 |
| [LLM LangGraph 多 Agent 设计](./superpowers/specs/2026-06-12-llm-langgraph-multi-agent-design.md) | vnpy-llm 编排层：Supervisor + Specialist + handoff |
| [LLM LangGraph 实施计划](./superpowers/plans/2026-06-12-llm-langgraph-phase1.md) | Phase 1–3 与收敛/打磨 checklist（已完成） |
| [编码规范](./coding-standards.md) | 代码风格、注释、分层约定 |
