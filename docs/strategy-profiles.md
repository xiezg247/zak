# 策略配置方案

> Profile 统一信号区、持仓区与 AI 默认策略。代码：`strategies/registry.py`、`config/preferences/watchlist_signal.py`。

---

## 1. 策略分层

四套 `Ashare*` 策略均保留，对应不同持股周期：

| 策略 | 周期 | 默认用途 |
|------|------|----------|
| `AshareShortBreakoutStrategy` | 1–5 日突破 | **全局默认** `short_swing` |
| `AshareDoubleMaStrategy` | 10/20 日 | 中线观察 `medium_watch` |
| `AshareSwingMaStrategy` | 1–4 周回踩 | 波段 |
| `AshareTrendMaStrategy` | 1–6 月趋势 | `trend` |

极致短线另有一套日 K / 分 K 策略（打板、半路、低吸、隔日退出），与上表**并存**，通过 Profile `ultra_short` 启用。

| 策略 | 模式 |
|------|------|
| `AshareLimitBoardStrategy` | 打板 |
| `AshareIntradayBreakoutStrategy` | 半路 |
| `AsharePullbackStrategy` | 低吸 |
| `AshareOvernightExitStrategy` | 持仓 overlay（非独立 CTA） |

---

## 2. Profile

| Profile | 信号 | 退出 | 环境 |
|---------|------|------|------|
| `ultra_short` | LimitBoard（可切 Pullback / IntradayBreakout） | OvernightExit overlay | 启动–高潮 |
| `short_swing` | ShortBreakout | 策略内止损止盈 | **默认** |
| `medium_watch` | DoubleMA | 双均线死叉 | 震荡观察 |
| `trend` | TrendMA | ADX + 追踪止损 | 回测、团队分析 |

持久化：`QSettings` `trading/strategy_profile`。切换时同步信号区 `class_name` 与硬过滤模板（ultra_short→激进；trend→保守；其余→均衡）。

---

## 3. UI

自选页 header：**策略 Profile** 下拉 → 同步信号区、硬过滤、持仓 `effective_config`。

新用户默认 `short_swing`；首次打开自选页可选其他风格。

---

## 4. 回测

所有 CTA 策略支持 `AShareTemplate`（T+1、整手、仅做多）。极致短线批量模板见 `backtest/batch_templates.py`。

---

## 5. AI

切换 Profile 时上下文附带 `strategy_profile`。`ultra_short` 须结合 `emotion_cycle` 与龙头上下文。

---

## 参考

[交易体系 §4](./trading-system.md) · [自选页](./watchlist.md)
