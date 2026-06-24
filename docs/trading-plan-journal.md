# 交易计划

> **纪律**：只做计划内交易；计划外操作须可识别。复盘以 [笔记流水](./stock-notes.md) + 持仓 Playbook 为主。  
> **2026-06 变更**：已移除 `trade_journal` 结构化流水及相关 UI / AI 工具；本文档仅保留 **TradingPlan** 与笔记复盘。

---

## 1. 复盘双轨（当前）

| 轨道 | 形态 | 状态 | 用途 |
|------|------|------|------|
| **笔记流水** | `stock_note_entries` 自由文本 | **已有** | 快速记录、AI 可读 |
| **次日计划** | `trading_plans` | **已有** | 盘前 3–5 只 + 仓位 + 条件 |
| ~~**交易流水**~~ | ~~`trade_journal`~~ | **已移除** | — |

与 [stock-notes.md](./stock-notes.md) 关系：笔记偏定性；计划偏**盘前纪律**。

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
│   ├── entry_conditions
│   └── exit_conditions
├── notes
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
写入 trading_plans + 同步自选池
      │
      ▼
盘前打开计划页 / 自选上下文条
      │
      ▼
盘中仅对 plan 内标的执行信号监控
      │
      ▼
登记持仓时校验：vt_symbol ∈ plan.watchlist ?
      └─ 否 → 计划外（toast / Playbook 提示）
```

### 2.3 UI

| 入口 | 说明 | 状态 |
|------|------|------|
| 雷达「生成次日计划」 | AI 草稿 → 确认对话框 | **已有** |
| 自选持仓「今日计划」 | 计划对话框编辑/激活 | **已有** |
| 笔记中心 Tab「计划」 | 历史计划列表 | **已有** |

---

## 3. 模式内亏损 vs 违规（概念）

| 类型 | 定义 | 当前表达 |
|------|------|----------|
| **模式内亏损** | 计划内 + 规则内执行仍亏损 | 笔记复盘 + Playbook |
| **违规操作** | off_plan、退潮买入、亏损补仓、浮亏扛单 | 登记时 toast；Playbook checklist |

自动打标（登记 / 计划校验）仍可用于 `off_plan` 等；**不再**写入 `trade_journal`。

---

## 4. 日复盘模板（30 分钟）

| 步骤 | 内容 | 工具 |
|------|------|------|
| 1 市场 | 涨跌停、连板、情绪阶段 | 市场页 + emotion_cycle |
| 2 计划执行 | 计划内几笔 / 计划外几笔 | trading_plans + 笔记 |
| 3 单笔 | 理由、模式、盈亏 | 笔记流水 |
| 4 次日 | 更新信号区/计划 + 新 plan | propose_trading_plan |

---

## 5. AI

| 工具 | 说明 | 状态 |
|------|------|------|
| `propose_trading_plan` | 输入：雷达共振、龙头、emotion；输出草案 | **已有** |
| `get_trading_plan` | 读当日/次日 active plan | **已有** |
| `evaluate_overnight_exit` | 隔日卖点检查 | **已有** |
| ~~`get_trade_journal`~~ | — | **已移除** |
| ~~`build_journal_prompt`~~ | — | **已移除** |
| ~~`get_trading_discipline_context`~~ | — | **已移除** |

---

## 6. Schema（计划表，**已有**）

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
```

> `trade_journal` 已不再建表；旧库残留表需手动清理。

---

## 7. 实施分期

| Phase | 交付 | 状态 |
|-------|------|------|
| 1 | 笔记 + 手动计划（无表） | 归档 |
| 2 | `trading_plans` + 同步自选 + 简单 UI | **已有** |
| 3 | ~~`trade_journal` + 登记联动~~ | **已移除** |
| 4 | AI propose/get + Playbook | **已有** |
| 5 | ~~流水明细 CRUD UI~~ | **已移除** |

---

## 参考

- [交易体系 §7](./trading-system.md#七复盘与纪律)
- [自选分组](./watchlist-groups.md)
- [交易辅助与风控提示](./risk-gate.md)
- [看盘页个股笔记](./stock-notes.md)
