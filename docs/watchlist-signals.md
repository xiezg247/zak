# 自选页策略信号区

## 1. 功能概述

自选页中部提供**独立策略信号区**：用户手动维护监控名单，基于双均线（可配快/慢线）展示买入/卖出/观望与参考价；与主表、图表、AI 联动；分层缓存与增量刷新。

| 项 | 约定 |
|----|------|
| 页面范围 | 仅自选页（`page_name == "自选"`，`show_watchlist_signals=True`） |
| 监控范围 | 信号区名单，**非**全自选池 |
| 策略 | 默认 `AshareDoubleMaStrategy`，快 10 / 慢 20 |
| 合规 | `SIGNAL_DISCLAIMER`：规则计算结果，仅供研究，不构成买卖建议 |
| 自选池上限 | 50 只（`WATCHLIST_MAX_ITEMS`） |
| 信号区上限 | 10 只（`SIGNAL_PANEL_MAX_SYMBOLS`） |

## 2. 布局

自选页中部采用纵向 `QSplitter`（`center_splitter`），自上而下：

```text
┌─────────────────────────────┐
│  自选主表（ExtendedSelection）│  stretch 4
├─────────────────────────────┤
│  策略信号区 WatchlistSignalPanel │  可折叠，默认展开
├─────────────────────────────┤
│  运行输出 TaskRunOutputPanel   │  可折叠，默认收起
└─────────────────────────────┘
```

工具栏保留 **「加入信号区」**；策略快/慢线、刷新、移出、清空在信号区 header。

尺寸同步见 `watchlist_signals/splitter.py`：折叠时信号区/运行输出约 32px，展开时分别约 180px / 160px，余量给主表。

## 3. 模块结构

```text
ui/quotes/watchlist_signals/
├── __init__.py      # barrel 导出
├── settings.py      # QSettings：策略参数、名单、启用、展开
├── panel.py           # WatchlistSignalPanel UI
├── controller.py      # WatchlistSignalController 刷新编排
├── worker.py          # WatchlistSignalWorker（QThread）
├── cache.py           # WatchlistSignalDiskCache（SQLite）
└── splitter.py        # center_splitter 尺寸
```

| 模块 | 路径 | 职责 |
|------|------|------|
| 快照模型 | `domain/signal_snapshot.py` | `SignalSnapshot`、缺 K 线 / stale 判定、行排序 |
| 批量计算 | `services/analysis_service.py` | `batch_strategy_signals()` 并行 map |
| 自选池 | `storage/app_db.py` | 50 上限、去重 |
| 页面壳 | `ui/quotes/page/` | QuotesPage、shell、config、run_log |
| 日 K 刷新 | `ui/quotes/controllers/local_data.py` | 下载/补缺口后 `refresh_symbols` |
| AI 问句 | `ai/context.py` | `build_signals_ai_prompt()` 对齐快/慢线 |
| 运行输出 | `ui/quotes/page/run_log.py` | 折叠持久化，与 splitter 协同 |

## 4. 数据流

```text
用户加入名单 (QSettings)
        │
        ▼
WatchlistSignalPanel.symbols
        │
        ▼
WatchlistSignalController.refresh()
        │
        ├─► 内存 cache 有效？ ──是──► panel.render()
        │
        ├─► 磁盘 cache 命中？ ──是──► 写入 signal_cache ──► render
        │
        └─► WatchlistSignalWorker
                 │
                 ▼
            AnalysisService.batch_strategy_signals()
            (run_parallel_map + pattern_load_max_workers)
                 │
                 ▼
            内存 cache + 磁盘 put_many ──► panel.render()
```

### 4.1 SignalSnapshot

| 字段 | 说明 |
|------|------|
| `signal` | `buy` / `sell` / `hold` / `na` |
| `as_of` | 计算所依据的 K 线最后交易日 |
| `ref_buy_price` / `ref_sell_price` | 规则参考价 |
| `strength` | 信号强度（排序用） |
| `warnings` | 含「K 线不足」等提示 |

辅助函数：`signal_missing_kline()`、`signal_as_of_stale()`、`signal_row_sort_key()`（买 > 观望 > 卖 > —，同档按强度、代码）。

### 4.2 内存缓存

`QuotesPage.signal_cache` + `_signal_cache_config`。

**有效条件**（`_cache_valid`）：

1. `_signal_cache_config == signal_config.normalized()`；
2. 快照 `strategy_id == class_name`；
3. `not signal_as_of_stale(snap, bar_end_date=本地日 K 末日)`。

### 4.3 磁盘短缓存

文件：`{用户数据目录}/watchlist_signal_cache.db`

主键：`(vt_symbol, config_key, bar_as_of)`，`config_key` = `"{class_name}:{fast}:{slow}"`。

Worker 完成后 `put_many`；`invalidate_cache()` 清空内存并 `DELETE` 磁盘表。配置变更触发全量失效。

### 4.4 增量刷新

| 场景 | 行为 |
|------|------|
| 定时器（5 分钟） | 仅 `_symbols_needing_refresh` |
| 手动「刷新」 | `force=True`，重算信号区全部标的 |
| 参数变更 | `invalidate_cache()` + `force=True` |
| 日 K 下载/补缺口 | 仅 `refresh_symbols` 受影响标的 |
| 名单变更 | 移除不在名单的 cache 项；对 miss 项 refresh |
| 禁用「启用信号」 | 停止 Worker 请求，仍 render 空态 |

并行度：`pattern_load_max_workers(item_count)`。

## 5. UI 交互

### 5.1 名单管理

| 操作 | 入口 | 行为 |
|------|------|------|
| 加入 | 主表多选 + 「加入信号区」 | 去重追加，满 10 只 toast 提示 |
| 移出 | 信号区选中 + 「移出」 | 确认后移除；无选中则尝试主表当前行 |
| 清空 | 「清空」 | 确认对话框后清空名单与相关 cache |

名单持久化：`QSettings` key `watchlist/signal_panel/symbols`（逗号分隔 vt_symbol）。

### 5.2 信号区表格

默认 **6 列**：代码、名称、信号、参考买价、参考卖价、强度。详情通过 tooltip / 域模型保留。

默认排序：`signal_row_sort_key`。统计栏可点击筛选买/卖/观望/缺日 K 数量。

### 5.3 联动

| 方向 | 行为 |
|------|------|
| 信号区单击/双击行 | 主表选中对应标的；图表 `apply_signal_reference(snap)` |
| 主表选中变化 | 信号区 `highlight_symbol` 高亮同行 |
| 问 AI（信号） | `build_signals_ai_prompt` 读取信号区快/慢线与 `class_name` |

### 5.4 折叠与持久化

| 状态 | QSettings key | 默认 |
|------|---------------|------|
| 信号区展开 | `watchlist/signal_panel/expanded` | true |
| 信号区启用 | `watchlist/signal_panel/enabled` | true |
| 运行输出展开 | `quotes/run_output/{page_name}/expanded` | false |

## 6. 刷新触发源

```text
定时器 (300s) → controller.refresh(force=False)
信号区「刷新」 → refresh(force=True)
快/慢线变更 → apply_config → invalidate_cache → force refresh
日 K 下载/补全/缺口填充 → local_data_controller → refresh_symbols(vt_list)
行情页加载完成 → data_loader_controller → on_symbols_changed
启用信号 toggle → on_panel_enabled_changed
```

## 7. AI 与工具对齐

自选页「问 AI（信号）」通过 `build_signals_ai_prompt()` 生成预填文案，参数来自信号区当前 `WatchlistSignalConfig`：

```text
list_strategy_signals(
  symbol="...",
  class_name="AshareDoubleMaStrategy",
  fast_window=10,
  slow_window=20
)
```

## 8. 测试

| 文件 | 覆盖 |
|------|------|
| `tests/ashare/ui/test_watchlist_signals.py` | settings、stale/missing kline、排序、磁盘 cache |
| `tests/ashare/test_app_db.py` | 自选池 50 上限 |
| `tests/ashare/ai/context/quote/test_prompts.py` | AI prompt 自定义 MA |
| `tests/ashare/ai/context/quote/test_assembly.py` | 看盘上下文 `build_quote_context` |
| `tests/llm/ui/test_floating_actions.py` | 悬浮球面板快捷动作路由 |

---

## 参考

- [自选多维看盘](./watchlist-multiview.md)
- [看盘页个股笔记](./stock-notes.md)
- [AI 功能与 K 线](./ai-kline-data.md)
