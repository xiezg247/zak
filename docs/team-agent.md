# 智能体投研团队

单票并行 **财务 / 风险 / 策略** 分析 + chief 汇总。与 `diagnose_stock` 快速诊断互补。

---

## 入口

| 方式 | 示例 |
|------|------|
| 命令 | `/team 600519` |
| 自然语言 | 「全面分析这只票」「团队分析」 |
| 深度模式 | AI 面板勾选「深度投研团队」 |

---

## 模式

| 模式 | 行为 |
|------|------|
| 快速（默认） | 预取 ≥2 维数据 → 直接出章节 + chief |
| 深度 | 三 Agent 并行 ReAct + chief（预取不足时自动降级） |

chief 须含短线环境（情绪阶段）；禁止具体买卖建议。

---

## 研报

chief 输出写入 `stock_analysis_reports`，对话内 `zak://team-report/{id}` 可在 [笔记中心](./stock-notes.md) 打开。

---

## 参考

[AI 数据路由](./ai-data-routing.md) · [架构说明](./architecture.md)
