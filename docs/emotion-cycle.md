# 情绪周期引擎

> **阶段**：框架期需求。择时模块核心：**先定环境再动手**。总纲见 [交易体系 §2](./trading-system.md#二择时体系情绪周期决定做不做)。
>
> **Blocker**：雷达龙头 gate、短线 Recipe R-04、持仓建议仓位、AI 择时均依赖本模块。

---

## 1. 与现有能力的关系

| 能力 | 路径 | 作用 | 与情绪周期的区别 |
|------|------|------|------------------|
| 市场广度 | `quotes/market/market_breadth.py` | 涨跌停、涨跌家数、成交额 | **输入源** |
| 恐贪指数 | `screener/sentiment/sentiment_gate.py` | 配方维度权重调制 | **因子级**，非总闸 |
| 北向 / 环境 | `quotes/market/market_environment.py` | 辅助参考 | 可选输入 |
| **情绪周期** | `quotes/market/emotion_cycle.py`（待建） | 五阶段标签 + 仓位系数 + 允许模式 | **总闸** |

```text
market_breadth + limit_ladder + index_ma5
              │
              ▼
       emotion_cycle.engine
              │
    ┌─────────┼─────────┬──────────────┐
    ▼         ▼         ▼              ▼
 顶栏芯片   选股 gate  雷达 gate    AI get_emotion_cycle
```

---

## 2. 五阶段定义

| 阶段 | 代号 | 量化条件（默认阈值，可 QSettings 校准） | 建议总仓位 | 允许模式 |
|------|------|----------------------------------------|------------|----------|
| 冰点 | `ice` | 最高连板 ≤ 2 **且** 跌停 ≥ 15 **且** 上涨家数占比 < 35% | 0%–10% | 无 / 极小试错 |
| 启动 | `startup` | 最高连板 ≥ 3 **或** 涨停 ≥ 50；未满足高潮条件 | 30%–50% | 首板、二板试错 |
| 发酵/高潮 | `climax` | 连板梯队 ≥ 3 层（如 5/3/2 板均有）**且** 涨停 ≥ 80 | 60%–80% | 龙头、前排跟风 |
| 分歧 | `divergence` | 最高连板断板 **或** 涨跌停家数差 ≤ 10 **且** 涨停 ≥ 30 | ≤ 30% | 核心低吸 |
| 退潮 | `recession` | 昨最高板今日跌停 **或** 连板批量断板（断板率 > 50%）**或** 跌停 ≥ 20 | **0%** | **禁止新开** |

**判定顺序**：退潮 → 冰点 → 高潮 → 分歧 → 启动 → 默认「分歧」（保守）。

### 2.1 输入字段

| 字段 | 来源 | 说明 |
|------|------|------|
| `limit_up_count` | `MarketBreadthSnapshot.limit_up` | 可切换 Tushare 精确值 |
| `limit_down_count` | 同上 | |
| `max_limit_times` | Redis `limit_times` 排行 max | 最高连板高度 |
| `limit_ladder_depth` | 连板分布统计 | 有几档连板（≥2 板家数 > 0 算一层） |
| `up_ratio` | up / (up+down) | 上涨占比 |
| `total_amount` | 两市成交额（元） | |
| `index_above_ma5` | 上证/深成 MA5 | 大盘 5 日线 |
| `fear_greed_index` | sentiment_gate | 辅助，不单独决定阶段 |

### 2.2 辅助系数（叠加，不替代阶段）

| 条件 | 动作 |
|------|------|
| 成交额 < 1 万亿 | 仓位系数 × 0.7 |
| 大盘 5 日线向下 | 仓位系数 × 0.8；模式去掉「打板」 |
| 恐贪 > 85 | 提示过热；不单独改阶段 |
| 监管敏感期（手动标记） | 回避高位连板提示 |

---

## 3. 输出模型

```python
# quotes/market/emotion_cycle.py（规划）

@dataclass(frozen=True)
class EmotionCycleSnapshot:
    stage: Literal["ice", "startup", "climax", "divergence", "recession"]
    stage_label: str              # 冰点 / 启动 / …
    position_pct_min: float       # 建议仓位下限
    position_pct_max: float       # 建议仓位上限
    position_factor: float        # 0.0–1.0，已含辅助系数
    allowed_modes: tuple[str, ...]  # limit_board | halfway | pullback
    allow_new_positions: bool     # 退潮 = False
    warnings: tuple[str, ...]
    inputs: dict[str, Any]        # 调试：原始计数
    updated_at: str
```

持久化：内存 + 可选写入 `context_store`（供 AI / 选股读取）；**不**落 zak.db（盘中重算）。

---

## 4. Gate 行为

| 消费者 | gate 规则 |
|--------|-----------|
| `run_leader_screen` | `recession` / `ice` → 空结果 + 原因文案 |
| 选股 Hub 批量入自选 | `recession` → 确认对话框 |
| 雷达卡片 subtitle | 追加「环境：发酵期 · 建议 5 成」 |
| 持仓登记 | `recession` → warning toast（不阻断记账） |
| Recipe `emotion_gate_only` | 退潮返回 Top 0–3 观察 |

---

## 5. UI

| 位置 | 组件 | 行为 |
|------|------|------|
| 市场页顶栏 | `EmotionCycleChip` | 阶段色：冰=蓝、启=绿、高潮=红、分歧=黄、退=灰 |
| 自选页顶栏 | 同上（只读） | 点击跳转市场页 |
| 雷达页顶栏 | 同上 + 允许模式 tooltip | |
| 阶段变更 | `emotion_stage_change` → 飞书（见 [消息通知](./notifications.md)） |

---

## 6. AI 与 Skill

| 工具 | 说明 |
|------|------|
| `get_emotion_cycle` | 返回 `EmotionCycleSnapshot` JSON |

Prompt 约束：退潮/冰点须明确「不建议短线新开仓」；须引用 `inputs` 中的涨跌停数，禁止编造。

---

## 7. 模块结构

```text
quotes/market/
├── market_breadth.py      # 已有
├── market_environment.py    # 已有
├── emotion_cycle.py         # 引擎 + load_emotion_cycle()
└── emotion_cycle_inputs.py  # 从 Redis / Tushare 聚合输入
```

---

## 8. 测试

| 用例 | 断言 |
|------|------|
| 退潮样本 | `allow_new_positions is False` |
| 高潮样本 | `position_factor >= 0.6` |
| 成交额不足 | factor 下调 |
| 边界 | 涨停 49 vs 50 不抖动（ hysteresis 可选 Phase 2） |

---

## 9. 实施分期

| Phase | 交付 |
|-------|------|
| 1 | 引擎 + 市场页芯片 + `get_emotion_cycle` |
| 2 | 雷达/选股 gate + 阈值设置 UI |
| 3 | 连板断板率、昨最高板跌停（需日切缓存） |

---

## 参考

- [交易体系需求](./trading-system.md)
- [盘中工作流](./intraday-workflow.md)
- [雷达选龙头 §8](./radar-leader-screening.md#8-情绪周期与硬过滤)
