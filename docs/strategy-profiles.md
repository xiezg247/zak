# 策略配置方案

> **阶段**：框架期。定义「短线为主、中线为辅」下**现有策略去留**、Profile 映射与 UI 切换。  
> 代码真源：`strategies/registry.py`、`strategies/signals.py`、`config/preferences/watchlist_signal.py`。

---

## 1. 结论：现有策略是否保留？

**全部保留。** 四套 `Ashare*` 策略已注册且信号链路完整，分别对应不同持股周期，与产品分层一致：

| 策略 | 周期定位 | 产品层级 | 建议 |
|------|----------|----------|------|
| `AshareShortBreakoutStrategy` | 1–5 日放量突破 | **短线波段（辅）** | **保留**；极致短线 Profile 的**日 K 信号**首选 |
| `AshareDoubleMaStrategy` | 10/20 日双均线 | **中线观察（辅）** | **保留**；稳健默认、回测验证 |
| `AshareSwingMaStrategy` | 1–4 周回踩 | 波段 | **保留**；分歧期「低吸」语义最接近 |
| `AshareTrendMaStrategy` | 1–6 月 ADX 趋势 | 中线 | **保留**；团队分析 / 趋势票验证 |

**不删除、不合并**现有策略。已通过 Profile 切换与极致短线规则层（打板/半路/隔日卖）与上述日 K CTA **并存**：

1. **默认 Profile**：全局默认 `medium_watch`；新用户经 onboarding 可引导「极致短线」（**已有**）
2. **信号区 / 持仓区 Profile 切换**（**已有**）：QSettings `trading/strategy_profile` + header 下拉
3. **硬过滤联动**（**已有**）：Profile 切换同步保守 / 均衡 / 激进模板

---

## 2. 为何不能只用一套策略？

| 维度 | 极致短线（规则层） | 现有 ShortBreakout | 现有 DoubleMA |
|------|----------------------|---------------------|---------------|
| 数据频率 | 分 K、涨停价、封板时间 | 日 K | 日 K |
| 持股 | 1–3 日，隔日卖铁则 | 1–5 日，止损止盈参数 | 趋势滞后 |
| 适用 | 龙头、连板、情绪博弈 | 放量突破活跃股 | 震荡过滤、中线底仓观察 |
| 回测 | 日 K 打板 CTA + 批量模板（**已有**） | **已有** CTA | **已有** CTA |

`AshareShortBreakoutStrategy` **不能替代**打板/半路/低吸：它不含涨停封板逻辑，也不含「高开低走 30 分钟止损」等隔日规则。

**极致短线策略族**（[交易体系 §4](./trading-system.md#四策略与买卖点量化规则拒绝主观) **已有**）：

| 策略 | 层级 | 与现有关系 |
|------|------|------------|
| `AshareLimitBoardStrategy` | 极致短线 · 打板 | 与 ShortBreakout 并存；`ultra_short` Profile 默认信号 |
| `AshareIntradayBreakoutStrategy` | 极致短线 · 半路 | 与 ShortBreakout 共用部分突破逻辑 |
| `AsharePullbackStrategy` | 极致短线 · 低吸 | 与 SwingMa 不同：Swing 是周级回踩 |
| `AshareOvernightExitStrategy` | 退出规则集 | **非独立 CTA**，绑定持仓区 overlay |

---

## 3. Profile 定义

用户级 **Strategy Profile** 统一信号区、持仓区、AI prompt 默认策略。

| Profile ID | 名称 | 信号策略 | 退出/持仓 | 典型环境 |
|------------|------|----------|-----------|----------|
| `ultra_short` | 极致短线 | `AshareLimitBoardStrategy`（打板）；`Pullback` / `IntradayBreakout` 可切换 | OvernightExit overlay（**已有**） | 启动–高潮 |
| `short_swing` | 短线波段 | `AshareShortBreakoutStrategy` | 同策略内止损止盈 | 分歧–发酵 |
| `medium_watch` | 中线观察 | `AshareDoubleMaStrategy` | 双均线死叉 | 自选默认（**当前**） |
| `trend` | 趋势中线 | `AshareTrendMaStrategy` | ADX + 追踪止损 | 回测、团队分析 |

**过渡说明（已 supersede）**：`ultra_short` Profile 已默认绑定 `AshareLimitBoardStrategy`；波段代理可手动切 `AshareShortBreakoutStrategy`。

---

## 4. 现有策略元数据速查

来源：`strategies/registry.py`

### 4.1 AshareDoubleMaStrategy

- **标签**：趋势跟踪、日 K  
- **适用**：均线趋势明显的蓝筹、中短期波段  
- **不适用**：横盘、极短周期  
- **信号**：`signals.build_signal_payload_for_strategy` → `double_ma`  
- **默认参数**：快 10 / 慢 20  

### 4.2 AshareShortBreakoutStrategy

- **标签**：短线、突破  
- **适用**：活跃股、题材龙头、1–5 日  
- **不适用**：低流动性、追涨停无法成交  
- **信号**：`short_breakout`；recent_days=2  
- **默认参数**：快 5 / 慢 10；breakout 5 日；量比 ≥ 1.5；max_hold 3 日  

### 4.3 AshareSwingMaStrategy

- **标签**：波段、回踩  
- **适用**：趋势明确、等待回踩、1–4 周  
- **信号**：`swing_ma`；金叉后缩量回踩慢线  

### 4.4 AshareTrendMaStrategy

- **标签**：趋势、ADX  
- **适用**：中期趋势、1–6 月  
- **信号**：`trend_ma`；ADX ≥ 25  

---

## 5. UI 与持久化（**已有**）

| 项 | QSettings key | 说明 |
|----|---------------|------|
| 全局 Profile | `trading/strategy_profile` | `ultra_short \| short_swing \| medium_watch \| trend` |
| 信号区覆盖 | `watchlist/signal_panel/*` | Profile 切换时批量写入 |
| 硬过滤联动 | `screener/hard_filter/*` | Profile 切换时同步保守/均衡/激进模板 |
| 持仓跟随 | `watchlist/position_panel/follow_signal` | true 时随信号区 |

**自选页 header**：

```text
策略 Profile [极致短线▾]  →  同步信号区 class_name + 硬过滤模板 + 持仓 effective_config
```

---

## 6. 回测页策略列表

| 策略 | 回测 | 短线主路径 |
|------|------|------------|
| DoubleMA | ✅ | 中线验证 |
| ShortBreakout | ✅ | **短线波段回测首选** |
| SwingMA | ✅ | 波段 |
| TrendMA | ✅ | 中线 |
| LimitBoard / IntradayBreakout / Pullback | ✅ | 极致短线；批量回测见 `backtest/batch_templates.py` |
| OvernightExit | overlay（非 CTA） | 持仓区绑定 |

回测与信号**共用** `AShareTemplate`（T+1、整手、仅做多）。

---

## 7. AI 对齐

| Profile | `list_strategy_signals` 默认 | prompt |
|---------|------------------------------|--------|
| ultra_short | LimitBoard（可切 Pullback / IntradayBreakout） | 须带 emotion_cycle + 龙头上下文 |
| medium_watch | DoubleMA | 现有 `build_signals_ai_prompt` |

切换 Profile 时 AI 上下文应附带 `strategy_profile` 字段。

---

## 8. 实施任务

| ID | 任务 | 状态 |
|----|------|------|
| SP-01 | Profile 枚举 + QSettings | 已有 |
| SP-02 | 信号区 Profile 下拉 | 已有 |
| SP-03 | 持仓区 header 展示 Profile | 已有 |
| SP-04 | 新用户默认 Profile + ultra_short onboarding 引导 | 已有 |
| SP-05 | LimitBoard / OvernightExit 策略与 registry | **已有** |
| SP-06 | Profile 切换同步硬过滤模板 | **已有** | ultra_short→激进；trend→保守；其余→均衡 |

---

## 参考

- [交易体系 §4、§4.3](./trading-system.md#43-策略配置方案用户级)
- [自选策略信号区](./watchlist-signals.md)
- [盘中工作流](./intraday-workflow.md)
