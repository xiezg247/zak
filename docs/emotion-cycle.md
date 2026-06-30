# 情绪周期引擎

择时总闸：**先定环境再动手**。总纲 [交易体系 §2](./trading-system.md#2-择时)。

`market_breadth` + 连板梯队 → `emotion_cycle.py` → 顶栏芯片 / 选股 gate / AI。恐贪经 `sentiment_gate` 调制配方权重。

---

## 五阶段

| 阶段 | 代号 | 建议仓位 | 允许模式 |
|------|------|----------|----------|
| 冰点 | `ice` | 0–10% | 极小试错 |
| 启动 | `startup` | 30–50% | 首板、二板 |
| 发酵/高潮 | `climax` | 60–80% | 龙头、跟风 |
| 分歧 | `divergence` | ≤30% | 核心低吸 |
| 退潮 | `recession` | **0%** | **禁止新开** |

判定顺序：退潮 → 冰点 → 高潮 → 分歧 → 启动。阈值在系统配置「情绪周期」Tab；支持迟滞。成交额 < 1 万亿或大盘 MA5 向下 → 下调仓位系数。

输出 `EmotionCycleSnapshot`（`stage`、`position_factor`、`allow_new_positions`、`warnings` 等）→ 内存 + `context_store`，不落库。

---

## Gate 与 UI

| 消费者 | 退潮/冰点 |
|--------|-----------|
| `run_leader_screen` | 空结果 |
| 选股批量入自选 | 确认对话框 |
| 持仓登记 | warning toast |
| `emotion_gate_only` Recipe | Top3 观察 |

顶栏 `EmotionCycleChip` 仅在市场页统计条展示。阶段变更可推飞书 `emotion_stage_change`。AI：`get_emotion_cycle`；退潮/冰点须明确不建议新开仓。

---

[市场页](./market-page.md) · [盘中工作流](./intraday-workflow.md) · [雷达选龙头](./radar-leader-screening.md)
