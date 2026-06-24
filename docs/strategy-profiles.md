# 策略配置方案

Profile 统一信号区、持仓区与 AI 默认策略。`strategies/registry.py`、`config/preferences/watchlist_signal.py`。

## 策略与 Profile

| Profile | 信号策略 | 退出 | 备注 |
|---------|----------|------|------|
| `ultra_short` | LimitBoard（可切 Pullback / IntradayBreakout） | OvernightExit overlay | 启动–高潮；联动激进硬过滤 |
| `short_swing` | ShortBreakout | 策略内止损止盈 | **默认** |
| `medium_watch` | DoubleMA | 双均线死叉 | 震荡观察 |
| `trend` | TrendMA | ADX + 追踪止损 | 回测、团队分析；保守硬过滤 |

另保留 SwingMA / TrendMa 等波段策略。极致短线日 K/分 K：`LimitBoard`、`IntradayBreakout`、`Pullback`、`OvernightExit`（overlay）。

持久化 `QSettings` `trading/strategy_profile`。自选 header 下拉切换 → 同步信号区 `class_name`、硬过滤模板、持仓 `effective_config`。回测均用 `AShareTemplate`；批量模板 `backtest/batch_templates.py`。

`ultra_short` 须结合 `emotion_cycle` 与龙头上下文。

---

[交易体系 §4](./trading-system.md#4-策略与买卖点) · [自选页](./watchlist.md) · [策略回测](./backtest-ux.md)
