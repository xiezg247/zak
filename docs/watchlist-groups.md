# 自选分组

> **交易风格**：服务 [盘中工作流](./intraday-workflow.md) 中「观察组 ≤5 只」；与自选池、信号区、持仓区分工不同。总纲见 [交易体系 §5、§3.5](./trading-system.md)。

---

## 1. 功能概述

自选页主表上方提供 **Tab 分组**：在**同一自选池（≤50 只）**内按标签筛选展示，不复制标的、不占用额外池容量。

| 项 | 约定 |
|----|------|
| 页面范围 | 仅自选页（`show_watchlist_group_tabs=True`） |
| 自选池 | 全局 `watchlist` 表，上限 50（`WATCHLIST_MAX_ITEMS`） |
| 分组数 | 最多 10 个（`WATCHLIST_MAX_GROUPS`） |
| 成员关系 | 多对多：一只票可属于多个分组 |
| 前置条件 | 标的须**已在自选池**才能加入分组 |

### 1.1 与短线工作流的分工

| 池/区 | 上限 | 用途 |
|-------|------|------|
| **自选池** | 50 | 总跟踪名单 |
| **分组·短线观察**（推荐预设名） | 文档建议 ≤5 | 次日计划候选（[交易体系](./trading-system.md)） |
| **信号区** | 10 | 当日规则监控 |
| **持仓记账** | 20 | 在途头寸 |

分组是**视图 + 标签**，不是第四套独立名单；雷达「加观察组」写入指定分组成员关系。

---

## 2. 布局

```text
┌─ WatchlistGroupTabBar ─────────────────────────────────────┐
│ [自选] | [短线观察] [龙头] [+]                               │
├────────────────────────────────────────────────────────────┤
│ 自选主表（分组激活时仅显示该组成员）                           │
│ 策略信号区 / 持仓区 / 运行输出（布局不变）                     │
└────────────────────────────────────────────────────────────┘
```

- **自选**：显示全部自选池（默认 Tab）。
- **分组 Tab**：筛选主表；排序调整仍须在「自选」Tab 下进行（上移/下移按钮 tooltip 提示）。

---

## 3. 模块结构

```text
storage/repositories/watchlist_groups.py   # CRUD、成员关系
ui/quotes/watchlist_groups/
├── prefs.py          # QSettings：active_group_id
├── tab_bar.py        # WatchlistGroupTabBar
├── controller.py   # WatchlistGroupController
└── dialog.py         # （预留扩展）
services/watchlist.py                        # list_groups / add_to_group 等门面
```

| 模块 | 职责 |
|------|------|
| `WatchlistGroupController` | Tab 切换、筛选 `all_stocks`、右键「加入分组」 |
| `WatchlistGroupTabBar` | 重建 Tab、新建/重命名/删除 |
| `WatchlistService` | 对 UI 暴露分组 API |

---

## 4. 数据模型

```sql
CREATE TABLE watchlist_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE watchlist_group_members (
    group_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    PRIMARY KEY (group_id, symbol, exchange),
    FOREIGN KEY (group_id) REFERENCES watchlist_groups(id) ON DELETE CASCADE
);
```

- 存储：`~/.vntrader/zak.db`
- 删除分组：仅删 `watchlist_groups` 行与成员关系，**不删**自选池标的
- 从自选池移除标的：自动 prune 各分组成员（`prune_watchlist_group_members`）

### 4.1 QSettings

| key | 说明 |
|-----|------|
| `watchlist/groups/active_group_id` | 当前激活分组；空 = 「自选」全量 |

---

## 5. 交互

| 操作 | 入口 | 行为 |
|------|------|------|
| 切换分组 | Tab 点击 | 筛选主表；持久化 active_group_id |
| 新建分组 | Tab 条 `+` | 输入名称；创建后自动激活 |
| 重命名 | 分组 Tab 右键 | |
| 删除 | 分组 Tab 右键 | 确认；标的保留在自选池 |
| 加入分组 | 主表右键 → 加入分组 | 多选批量；勾选/取消各分组 |
| 雷达加观察组 | 规划：龙头卡 footer | 需先加入自选，再写入「短线观察」分组 |

### 5.1 筛选逻辑

```text
watchlist_pool_stocks（全量 50）
        │
        ▼
WatchlistGroupController.filter_stocks()
        │
        ├─ active_group_id 为空 → 全量
        └─ 否则 → member_keys 交集
        │
        ▼
page.all_stocks → apply_filter()
```

`filtered_vt_symbols()` 供导出/AI 上下文（激活分组时）。

---

## 6. 与雷达 / 选股联动（规划）

| 来源 | 行为 | 状态 |
|------|------|------|
| 雷达 `leader_pick` | 「加观察组」→ 默认分组名「短线观察」 | **已有** |
| 选股结果 | 结果操作条「加入观察组」 | **已有** |
| 次日计划 | TradingPlan.watchlist 同步到该分组 | **待建** |

**预设分组建议**（首次引导，非强制）：

| 名称 | 用途 |
|------|------|
| 短线观察 | 3–5 只计划内候选 |
| 龙头跟踪 | 雷达龙一/共振 |

---

## 7. AI 上下文（规划）

| 字段 | 说明 |
|------|------|
| `active_watchlist_group` | 当前 Tab 名称 |
| `group_symbols` | 激活时分组成员 vt_symbol 列表 |

工具：`get_short_term_watchlist`（**已有**，vnpy-watchlist）。

---

## 8. 边界与限制

| 项 | 约定 |
|----|------|
| 分组不能超自选池 | `add_watchlist_group_member` 要求 watchlist 行存在 |
| 分组筛选 vs 搜索 | 搜索在筛选后的 `all_stocks` 上生效 |
| 与信号区名单 | **独立**；信号区仍用 QSettings 逗号名单 |
| 与持仓 | 持仓区显示全部记账头寸，不随分组 Tab 隐藏（规划：可选「仅观察组持仓」筛选） |

---

## 9. 测试

| 文件 | 覆盖 |
|------|------|
| `tests/ashare/test_app_db.py` | schema、分组 CRUD |
| `tests/ashare/ui/test_watchlist_controller.py` | 分组菜单、筛选 |

---

## 参考

- [盘中工作流](./intraday-workflow.md)
- [雷达选龙头](./radar-leader-screening.md)
- [自选策略信号区](./watchlist-signals.md)
