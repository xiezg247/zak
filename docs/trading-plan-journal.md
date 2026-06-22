# 交易计划与流水

> **纪律**：只做计划内交易；计划外操作须可标记、可统计。复盘闭环见 [盘中工作流 §3.3](./intraday-workflow.md)。笔记流水与结构化流水**并存**。

---

## 1. 双轨复盘

| 轨道 | 形态 | 状态 | 用途 |
|------|------|------|------|
| **笔记流水** | `stock_note_entries` 自由文本 | **已有** | 快速记录、AI 可读 |
| **交易流水** | `trade_journal` 结构化 | **已有** | 胜率、盈亏比、违规统计；**可查看 / 编辑 / 删除** |
| **次日计划** | `trading_plans` | **已有** | 盘前 3–5 只 + 仓位 + 条件 |

与 [stock-notes.md](./stock-notes.md) 关系：笔记偏定性；本模块偏**可聚合字段**。

---

## 2. 交易计划 TradingPlan

### 2.1 实体

```text
TradingPlan
├── id
├── trade_date          # 计划适用交易日（通常 T+1 执行）
├── created_at
├── emotion_expected    # 预期情绪阶段 ice|startup|…
├── max_position_pct    # 计划总仓位 0–80
├── watchlist           # vt_symbol[]，建议 3–5
├── per_symbol[]
│   ├── vt_symbol
│   ├── allowed_modes[] # limit_board | halfway | pullback
│   ├── entry_conditions   # JSON 或结构化文本
│   └── exit_conditions
├── notes               # 备忘
└── status              # draft | active | archived
```

存储：`zak.db` 表 `trading_plans` + `trading_plan_symbols`（**已有**）。

### 2.2 工作流

```text
盘后 AI / 手动
      │
      ▼
propose_trading_plan → 用户确认
      │
      ▼
写入 trading_plans + 同步自选池（计划标的 ensure 在 watchlist）
      │
      ▼
盘前打开计划页 / 自选上下文条
      │
      ▼
盘中仅对 plan 内标的执行信号监控
      │
      ▼
登记持仓时校验：vt_symbol ∈ plan.watchlist ?
      ├─ 否 → 流水标记 off_plan
      └─ 是 → mode 匹配 allowed_modes ?
```

### 2.3 UI

| 入口 | 说明 | 状态 |
|------|------|------|
| 雷达「生成次日计划」 | AI 草稿 → 确认对话框 | **已有** |
| 自选持仓「今日计划」 | 计划对话框编辑/激活 | **已有** |
| 笔记中心 Tab「计划」 | 历史计划列表 | **已有** |

---

## 3. 交易流水 trade_journal

### 3.1 实体

```text
TradeJournalEntry
├── id
├── symbol / exchange
├── vt_symbol
├── side                # buy | sell
├── trade_date          # 成交日记账日
├── price
├── volume
├── amount
├── mode                # limit_board | halfway | pullback | swing | other
├── plan_id             # nullable，关联 TradingPlan
├── on_plan             # bool
├── violation_tags[]    # off_plan | recession_buy | add_loss | …
├── pnl                 # sell 时已实现盈亏（元）
├── pnl_pct
├── reason              # 用户简述
├── emotion_stage       # 登记时 emotion_cycle.stage
└── created_at
```

### 3.2 与持仓记账关系

| 事件 | 动作 |
|------|------|
| 登记持仓（买） | 可选自动写 buy 流水；关联 plan |
| 删除/清零持仓（卖） | 写 sell 流水 + realized_pnl |
| 仅笔记流水 | 不替代 trade_journal；右键「导入交易流水」**已有** |

`watchlist_positions` 仍是**当前头寸**；`trade_journal` 是**历史事件**。

### 3.3 UI 入口（查看 / 编辑 / 删除）

| 入口 | 路径 | 说明 | 状态 |
|------|------|------|------|
| **复盘 · 流水明细** | 自选持仓区 **「复盘」** → Tab「流水明细」 | 与统计同区间；双击编辑、右键删除；改后刷新风控闸 | **已有** |
| **笔记中心 · 交易流水** | `Ctrl+Shift+N` → Tab **「交易流水」** | 跨标的结构化流水；默认近 30 天；左侧选标的可过滤 | **已有** |
| **风控 · 登记卖出** | 顶栏风控芯片 / 持仓 **「风控设置」** → 高级 **「查看…」** | 今日 `side=sell` 流水；汇总行随编辑自动更新 | **已有** |

落点：

- 明细表：`ui/quotes/watchlist_positions/trade_journal_manage_view.py`
- 编辑：`trade_journal_edit_dialog.py`
- 独立打开：`trade_journal_open.py`（`show_today_sell_journal` 等）
- 维护逻辑：`trading/journal/maintain.py`（更新时卖出单按最近 buy 流水重算 `pnl` / `pnl_pct`）

### 3.4 编辑与删除约定

| 操作 | 行为 | 下游影响 |
|------|------|----------|
| **编辑卖出** | 可改成交日、价格、数量、理由、模式、计划内、违规标签 | `pnl` 按最近买入流水成本重算 |
| **删除** | 二次确认 | `sum_realized_pnl_for_date`、风控闸当日盈亏、扛单检测（`has_sell_journal_since`） |
| **笔记流水** | 仍只追加；右键「导入交易流水」写入 `trade_journal` | 与明细管理互补，不替代 |

> **未做**：不经删持仓的「手动补录卖出」、AI `get_trade_journal` 的写操作。

---

## 4. 模式内亏损 vs 违规

| 类型 | 定义 | 统计 |
|------|------|------|
| **模式内亏损** | 计划内 + 规则内执行仍亏损 | 计入策略胜率 |
| **违规操作** | off_plan、退潮买入、亏损补仓等 | 单独计数，复盘重点 |

违规自动打标来源：

| tag | 触发 |
|-----|------|
| `off_plan` | 买入不在 plan.watchlist |
| `recession_buy` | emotion=recession |
| `float_loss_hold` | 浮亏 ≤−5% 且无 sell 流水 |
| `add_loss` | 同标的加仓且前笔浮亏 |

---

## 5. 日复盘模板（30 分钟）

| 步骤 | 内容 | 工具 |
|------|------|------|
| 1 市场 | 涨跌停、连板、情绪阶段 | 市场页 + emotion_cycle |
| 2 计划执行 | 计划内几笔 / 违规几笔 | trading_plans + journal |
| 3 单笔 | 理由、模式、盈亏 | 笔记 + journal；误记可在 **流水明细** 修正 |
| 4 次日 | 更新信号区/计划 + 新 plan | propose_trading_plan |

---

## 6. AI

| 工具 | 说明 |
|------|------|
| `propose_trading_plan` | 输入：雷达共振、龙头、emotion；输出草案 |
| `get_trading_plan` | 读当日/次日 active plan |
| `get_trade_journal` | 区间查询、违规汇总 |
| `build_journal_prompt` | 盘后一键复盘预填 |

上下文注入：`context_store` 增加 `trading_plan_summary`、`journal_today_count`。

---

## 7. 报表（J-05，**已有**）

| 指标 | 公式 |
|------|------|
| 胜率 | wins / (wins + losses) |
| 盈亏比 | avg_win / abs(avg_loss) |
| **模式内胜率** | 计划内且无违规的卖出 wins / losses |
| **模式内盈亏比** | 模式内 avg_win / abs(avg_loss) |
| 模式内占比 | on_plan trades / total |
| 违规率 | violation trades / total |

对齐 [交易体系 §1.2](./trading-system.md) 极致短线合理区间：胜率 40–55%，盈亏比 ≥ 2:1。

---

## 8. Schema（**已有**）

> 建表逻辑见 `storage/connection.py`；下列为字段参考（与实现略有命名差异，如 `allowed_modes_json`）。

```sql
CREATE TABLE trading_plans (
    id TEXT PRIMARY KEY,
    trade_date TEXT NOT NULL,
    emotion_expected TEXT NOT NULL DEFAULT '',
    max_position_pct REAL NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE trading_plan_symbols (
    plan_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    allowed_modes TEXT NOT NULL DEFAULT '',
    entry_conditions TEXT NOT NULL DEFAULT '',
    exit_conditions TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (plan_id, symbol, exchange),
    FOREIGN KEY (plan_id) REFERENCES trading_plans(id) ON DELETE CASCADE
);

CREATE TABLE trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    side TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    price REAL NOT NULL,
    volume INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT '',
    plan_id TEXT,
    on_plan INTEGER NOT NULL DEFAULT 0,
    violation_tags TEXT NOT NULL DEFAULT '',
    pnl REAL,
    pnl_pct REAL,
    reason TEXT NOT NULL DEFAULT '',
    emotion_stage TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
```

---

## 9. 实施分期（均已交付）

| Phase | 交付 | 状态 |
|-------|------|------|
| 1 | 笔记 + 手动计划（无表） | 归档 |
| 2 | `trading_plans` + 同步自选 + 简单 UI | **已有** |
| 3 | `trade_journal` + 登记联动 + off_plan 标记 | **已有** |
| 4 | AI propose/get + 周度报表（J-05） | **已有** |
| 5 | 流水明细 CRUD UI（复盘 / 笔记中心 / 风控） | **已有** |

---

## 参考

- [交易体系 §7](./trading-system.md#七复盘与纪律)
- [自选分组](./watchlist-groups.md)
- [风控体系](./risk-gate.md)
- [看盘页个股笔记](./stock-notes.md)
