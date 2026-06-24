# 自选页持仓区

> **UI 架构**（`features/watchlist/`、Host 协议、持仓专注模式）见 [watchlist-ui.md](./watchlist-ui.md)。  
> **定位**：投研**记账 + 规则退出参考**，非券商实盘同步。服务极致短线 **隔日卖点** 与 T+1 约束。策略 Profile 见 [策略配置方案](./strategy-profiles.md)。

---

## 1. 功能概述

自选页中部 **持仓区**（`WatchlistPositionPanel`）：登记成本、数量、买入日；结合行情与策略信号展示浮盈、T+1 状态、退出信号与异动标签。

| 项 | 约定 |
|----|------|
| 页面范围 | 自选页（`show_watchlist_positions=True`） |
| 上限 | 20 只（`POSITION_MAX_ITEMS`） |
| 数据源 | `watchlist_positions` @ zak.db |
| 合规 | 规则参考价 + `SIGNAL_DISCLAIMER` |
| 与笔记 | 持仓 `notes` 字段 **不合并** 笔记中心（见 [stock-notes.md](./stock-notes.md)） |

---

## 2. 布局

与信号区共用 `center_splitter`（见 [watchlist-signals.md §2](./watchlist-signals.md#2-布局)）：

```text
┌─ 自选主表 ─────────────────┐
├─ 策略信号区 ───────────────┤
├─ 持仓区 WatchlistPositionPanel │
├─ 运行输出 ─────────────────┤
└────────────────────────────┘
```

### 2.1 表格列（默认）

| 列 | 说明 |
|----|------|
| 代码 / 名称 | |
| 成本价 / 持仓量 / 买入日 | 登记字段 |
| 现价 / 浮盈 / 浮盈% | 实时行情计算 |
| T+1 | 「T+1 锁定」/「可卖」 |
| 退出信号 | 策略 buy/sell/hold |
| 参考卖价 | 来自 `SignalSnapshot.ref_sell_price` |
| 隔日规则 | `exit_rules` 列：触发 / 临近 / 未触发（`ultra_short` Profile + overlay） |
| 异动 | 名称列角标 / tooltip（`position_anomaly.py`） |

**header**（[交易体系 §5.3](./trading-system.md) **已有**）：策略 Profile 下拉、情绪建议仓位 vs 实际、筛选（待卖 / T+1 锁 / 浮亏）。

---

## 3. 模块结构

```text
domain/position_snapshot.py          # PositionRecord / PositionSnapshot
storage/repositories/positions.py    # CRUD
config/preferences/watchlist_position.py
ui/quotes/watchlist_positions/
├── panel.py
├── controller.py
├── worker.py          # WatchlistPositionWorker
├── cache.py           # 磁盘短缓存
└── dialog.py          # PositionEditDialog
quotes/misc/position_anomaly.py      # 异动标签
```

---

## 4. 数据模型

```sql
CREATE TABLE watchlist_positions (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    cost_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    buy_date TEXT NOT NULL,      -- YYYY-MM-DD
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',  -- manual | gateway | paper（预留）
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, exchange)
);
```

### 4.1 PositionSnapshot 字段

| 字段 | 说明 |
|------|------|
| `t1_locked` | 买入日 ≥ 当日 → 不可卖提示 |
| `exit_signal` | 绑定策略的 sell/hold/buy |
| `exit_ref_price` / `dist_exit_pct` | 距参考卖价 |
| `signal_snapshot` | 完整策略快照 |
| `warnings` | K 线不足等 |

计算：`build_position_snapshot()` @ `domain/position_snapshot.py`。

---

## 5. 策略与 Profile

| 配置 | QSettings | 默认 |
|------|-----------|------|
| 启用面板 | `watchlist/position_panel/enabled` | true |
| 展开 | `watchlist/position_panel/expanded` | true |
| 跟随信号区策略 | `watchlist/position_panel/follow_signal` | true |
| 独立策略 | `watchlist/position_panel/strategy` | `AshareDoubleMaStrategy` |

`follow_signal=true` 时，退出信号与信号区 `WatchlistSignalConfig` 一致；否则用持仓区独立 class_name / 快慢线。

**极致短线**：Profile=`ultra_short` 时持仓 overlay 绑定 `AshareOvernightExitStrategy` 规则集（**已有**）；AI 工具 `evaluate_overnight_exit`。

---

## 6. 异动检测（已有）

`position_anomaly.py` 阈值：

| 标签 | 条件 |
|------|------|
| 卖出信号 | `exit_signal == sell` |
| 急跌 | 日内涨幅 ≤ −3% |
| 大涨 | 日内 ≥ 5% 或接近涨停 |
| 放量 | 量比 ≥ 1.2 且 \|涨跌\| ≥ 1.5% |
| 浮亏 | 浮盈% ≤ −5% |
| 浮盈 | 浮盈% ≥ 15% |
| 开盘止损 | 该高开却低开，30 分钟不翻红（**已有**；`opening_stop` + 分 K 优先） |
| 浮亏扛单 | 浮亏超阈仍 hold（**已有**；流水违规联动） |

**隔日规则列**（`overnight_exit` **已有**，与异动标签分工）：

| 规则 | 条件 |
|------|------|
| 开盘止损 | 同「开盘止损」异动 |
| 低开走弱 | 低开且现价低于开盘 / 昨收 |
| 冲高量能不足 | 开盘冲高 3–5% 且量比不足（near） |
| 涨停打开 | 炸板回封无力 → sell |
| 上午必卖 | 11:00 后 / 下午仍持仓且弱势或隔日规则 near/triggered（**已有**，异动标签） |

> **状态（2026-06）**：隔日规则列 + 异动标签（含「上午必卖」）**已有**；与 `exit_signal=sell` / 「开盘止损」分工，避免重复提醒。

---

## 7. 刷新与缓存

与信号区类似：

| 触发 | 行为 |
|------|------|
| 定时器 | 增量刷新持仓名单 |
| 手动刷新 | force 重算 |
| 策略参数变更 | invalidate + 全量 |
| 行情 tick | 现价 / 浮盈 / 异动 |

磁盘缓存：`watchlist_position_cache.db`（config_key 含策略参数）。

---

## 8. 交互

| 操作 | 行为 |
|------|------|
| 登记持仓 | 主表选中 → 「登记持仓」→ `PositionEditDialog` |
| 补录卖出 | 选中持仓 → 「补录卖出」→ 写 sell 流水；持仓保留；分批卖出时同步减量 |
| 移出 / 编辑 | 持仓区工具栏「移出」「编辑」 |
| 单击行 | 联动主表、图表 |
| 统计栏筛选 | 待卖 / T+1 锁 / 浮亏（已有 filter） |

---

## 9. 与短线工作流

```text
雷达龙头 → 自选池 → 信号区监控 → 登记持仓
                              │
                              ▼
                    T+1 锁定 + 隔日 exit 规则（**已有**，overlay + AI）
                              │
                              ▼
                    笔记流水复盘 + Playbook（**已有**）
```

登记时：`emotion_cycle` 退潮期 toast 警告（**已有**）；总资金参数供仓位 % 列（见 [risk-gate.md](./risk-gate.md)）。

---

## 10. AI

| 入口 | prompt |
|------|--------|
| 问 AI（持仓） | `build_positions_ai_prompt` — 含成本、浮盈、T+1、退出信号 |
| 隔日卖点检查 | `evaluate_overnight_exit` ✅ | 登记持仓 + 实时行情 |

---

## 参考

- [交易体系 §4.2、§5](./trading-system.md)
- [自选策略信号区](./watchlist-signals.md)
- [风控体系](./risk-gate.md)
