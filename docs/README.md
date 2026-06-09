# zak 文档

| 文档 | 说明 |
|------|------|
| [产品方案](./product-plan.md) | **北极星**：回测 + 看盘 + AI + 选股 + A 股策略实盘 |
| [策略回测交互规格](./backtest-ux.md) | 看盘→回测联动（B1✅）、摘要落库（B3✅）、回测 AI 上下文（B4✅）、批量回测（B2 待做） |
| [架构说明](./architecture.md) | 与 vnpy 默认 Trader 的关系、当前 UI 分层、Service 层 |
| [数据设计](./data-design.md) | 三个 SQLite 数据库 + Redis 缓存层设计 |
| [AI 数据路由说明](./ai-data-routing.md) | AI 助手各类问题对应的数据源与工具 |
| [后续规划](./roadmap.md) | P3 策略实盘、P4 Gateway 看盘、PaperAccount 等 |

## 技术规格

| 文档 | 说明 |
|------|------|
| [AI 能力重构设计方案](./superpowers/specs/2026-06-08-ai-refactor-design.md) | Service 层、Skills 拆分、context_store（**已实现**） |
| [悬浮球功能增强设计](./superpowers/specs/2026-06-08-floating-orb-enhancement-design.md) | 上下文 Chip、Quick Actions、FloatingAiController（Phase 1–3 已实现） |
| [本地页 K 线覆盖设计](./superpowers/specs/2026-06-07-local-data-coverage-design.md) | K 线数据健康检测、补全交互 |
| [AI 重构实现计划](./superpowers/plans/2026-06-08-ai-refactor-plan.md) | 分步实施记录（**已完成**，checkbox 仅作历史参考） |
