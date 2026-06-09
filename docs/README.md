# zak 文档

## 项目状态（2026-06）

**投研终端已基本就绪**：看盘、K 线下载、选股、策略回测（含批量对比）、AI 助手（Skills + MCP + 多会话 + 流式中断）、配置热重载均已落地。

**远期规划（暂无近期计划）**：P3 策略实盘、PaperAccount 模拟盘、P4 Gateway 看盘行情 — 设计保留在 [roadmap.md](./roadmap.md)，当前不排期。

---

## 产品与交互

| 文档 | 说明 |
|------|------|
| [产品方案](./product-plan.md) | 北极星：四支柱投研闭环 ✅；策略实盘为远期备忘 |
| [策略回测交互规格](./backtest-ux.md) | B1–B4 已实现（联动、批量回测、摘要落库、AI 上下文） |
| [AI 数据路由说明](./ai-data-routing.md) | 各类问题对应的 Skill / MCP / 数据源 |

---

## 架构与数据

| 文档 | 说明 |
|------|------|
| [架构说明](./architecture.md) | GUI 分层、Service 层、行情 Provider、AI 上下文 |
| [数据设计](./data-design.md) | 三个 SQLite + Redis + `context_store` 内存态 |
| [演进路线](./roadmap.md) | P0–P2 ✅；P3–P4 远期规划（暂无近期计划） |

---

## 设计档案（已实现，供追溯）

| 文档 | 说明 |
|------|------|
| [AI 能力重构设计](./design/specs/2026-06-08-ai-refactor-design.md) | Service 层、Skills 拆分、context_store |
| [悬浮球功能增强设计](./design/specs/2026-06-08-floating-orb-enhancement-design.md) | ContextChip、Quick Actions、FloatingAiController |
| [本地页 K 线覆盖设计](./design/specs/2026-06-07-local-data-coverage-design.md) | `bar_health` 健康检测与补全交互 |
| [AI 重构实施记录](./design/plans/2026-06-08-ai-refactor-plan.md) | 分步 checkbox 历史（**已完成**） |
