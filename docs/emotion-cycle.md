# 情绪周期引擎

> 择时总闸：**先定环境再动手**。总纲见 [交易体系 §2](./trading-system.md#2-择时)。

---

## 1. 与相关模块

| 模块 | 路径 | 角色 |
|------|------|------|
| 市场广度 | `market_breadth.py` | 输入 |
| 恐贪 | `sentiment_gate.py` | 配方权重调制 |
| 情绪周期 | `emotion_cycle.py` | 五阶段 + 仓位系数 |

```text
market_breadth + limit_ladder → emotion_cycle → 顶栏芯片 / 选股 gate / AI
```

---

## 2. 五阶段

| 阶段 | 代号 | 建议仓位 | 允许模式 |
|------|------|----------|----------|
| 冰点 | `ice` | 0–10% | 极小试错 |
| 启动 | `startup` | 30–50% | 首板、二板 |
| 发酵/高潮 | `climax` | 60–80% | 龙头、跟风 |
| 分歧 | `divergence` | ≤30% | 核心低吸 |
| 退潮 | `recession` | **0%** | **禁止新开** |

判定顺序：退潮 → 冰点 → 高潮 → 分歧 → 启动。阈值可在系统配置 →「情绪周期」Tab 校准；支持阶段迟滞（hysteresis）。

辅助：成交额 < 1 万亿、大盘 MA5 向下 → 下调仓位系数。

---

## 3. 输出 EmotionCycleSnapshot

`stage`、`position_pct_min/max`、`position_factor`、`allowed_modes`、`allow_new_positions`、`warnings`。  
内存 + `context_store`；不落 zak.db。

---

## 4. Gate 消费者

| 消费者 | 规则 |
|--------|------|
| `run_leader_screen` | 退潮/冰点 → 空结果 |
| 选股批量入自选 | 退潮 → 确认对话框 |
| 持仓登记 | 退潮 → warning toast |
| `emotion_gate_only` Recipe | 退潮 Top3 观察 |

---

## 5. UI

市场/自选/雷达顶栏 `EmotionCycleChip`。阶段变更可推送飞书（`emotion_stage_change`）。

---

## 6. AI

`get_emotion_cycle` 返回快照 JSON。退潮/冰点须明确不建议短线新开仓。

---

## 参考

[市场页](./market-page.md) · [盘中工作流](./intraday-workflow.md) · [雷达选龙头](./radar-leader-screening.md)
