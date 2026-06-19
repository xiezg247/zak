# 自选页 UI 架构

> 自选页（`page_name == "自选"`）的 toolbar、中部布局与工作流预设由 `features/watchlist/` 封装；子模块（信号区、持仓区、多维等）通过 **Host 协议** 访问 `QuotesPage` 能力，避免直接耦合整页。

相关专题文档：[信号区](./watchlist-signals.md) · [持仓区](./watchlist-positions.md) · [多维看盘](./watchlist-multiview.md) · [分组 Tab](./watchlist-groups.md)

---

## 1. `features/watchlist/` 目录

```text
ui/quotes/features/watchlist/
├── page_feature.py       # WatchlistPageFeature：生命周期、预设切换、上下文条
├── center_layout.py      # 中部布局（分组 Tab、上下文条、splitter）
├── context_bar.py        # 四层池摘要条；点击段切换视图 / 持仓专注
├── layout_preset.py      # apply_layout_preset / apply_position_focus
├── preset_specs.py       # 盘中 / 登记 / 复盘 规格表
├── prefs.py              # 布局预设 QSettings
├── toolbar.py            # 工具栏控件与自选动作收拢
├── toolbar_policy.py     # 自选页工具栏 policy（轻量，供 shell / 单测）
└── toolbar_preset.py     # 预设驱动工具栏显隐（登记、chip 等）
```

| 模块 | 职责 |
|------|------|
| `WatchlistPageFeature` | 自选页入口：`on_activate`、预设下拉、上下文条刷新 |
| `build_watchlist_center_layout` | 挂载分组 Tab、上下文条、`center_splitter` |
| `apply_layout_preset` | 盘中 / 登记 / 复盘：面板折叠、Tab、视图、工具栏 |
| `apply_position_focus` | 点击「持仓 n/20」：信号折叠 + 持仓展开 + 主表 25% |
| `WatchlistToolbarPolicy` | 自选页将回测/排序/下载等收入右键或「更多」 |

---

## 2. Host 协议

Host 协议定义在 `ui/quotes/watchlist/`，分层如下：

```text
WatchlistPoolHost          # 跨页：WatchlistController 所需最小接口
    ↑
WatchlistHost              # 自选页：信号/持仓/多维 controller 与 panel
```

### 2.1 `WatchlistPoolHost`

供 `WatchlistController`（加入/移出自选、排序）使用，**不限于自选页**。

主要字段：`watchlist_pool_stocks`、`quote_map`、`position_cache`、`_signals`、自选按钮等。  
主要方法：`_get_watchlist_service()`、`apply_filter()`、`_update_action_buttons()`。

### 2.2 `WatchlistHost`

扩展池 Host，供信号/持仓/多维/分组 controller 与 `WatchlistPageFeature` 使用。

| 类别 | 成员示例 |
|------|----------|
| 数据 | `signal_cache`、`position_cache`、`bar_meta`、`display_stocks` |
| UI | `market_table`、`signal_panel`、`position_panel`、`multiview_board`、`_center_splitter` |
| Controller | `_signals`、`_positions`、`_multiview`、`_watchlist_groups` |
| 生命周期 | `find_stock_item()`、`apply_strategy_profile()`、`_wire_signal_panel()` 等 |

`QuotesPage` 在自选页场景下满足 `WatchlistHost`；controller 构造函数参数类型为 `WatchlistHost`，便于单测 mock。

### 2.3 刷新调度

`ui/quotes/watchlist/refresh_scheduler.py`：`WatchlistStrategyRefreshScheduler` 用**单 QTimer** 驱动信号区与持仓区 `refresh(force=False)`，由 `QuotesPage` 在 activate/deactivate 时启停。

`ui/quotes/watchlist/bootstrap.py`：`WatchlistBootstrapCoordinator` 作为自选页**加载编排入口**：

- `on_activate`：自选池 fingerprint 未变时走增量同步（不触发 `UniverseLoadWorker`）
- `on_pool_ready`：全量/增删自选后统一调度 groups → context_bar → 下游刷新
- `schedule_downstream`：按布局预设（盘中/登记/复盘）决定信号/持仓/多维的加载优先级；折叠面板在 `force=False` 时不启策略 worker

`ui/quotes/watchlist/strategy_batch.py`：`WatchlistStrategyBatchCoordinator` 合并信号区与持仓区**相同 `cache_key`** 的待算标的，单次 `batch_strategy_signals` 后分别写入两区缓存；持仓不跟随信号（独立 Profile）时仍分两次计算。

---

## 3. 工作流预设

工具栏下拉：**盘中** / **登记** / **复盘**（`preset_specs.py`）。

| 预设 | 信号区 | 持仓区 | 主表比例 | 工具栏 |
|------|--------|--------|----------|--------|
| 盘中 | 展开 | 折叠 | 默认（余量给主表） | 隐藏「登记持仓」；情绪/风控 chip 在栏内 |
| 登记 | 展开 | 展开 | 默认 | 显示登记 + 加入信号 |
| 复盘 | 折叠 | 展开 | 40% | 隐藏「加入信号」；chip 收到「更多」 |

**持仓专注**（非预设）：点击上下文条「持仓 n/20」→ `apply_position_focus()`：信号折叠、持仓展开、主表 **25%**（`POSITION_FOCUS_TABLE_RATIO`），不改变预设下拉选中项。

---

## 4. 与 `shell.py` 的分工

| 位置 | 内容 |
|------|------|
| `shell.py` | 通用 QuotesPage 控件创建、表格、右侧详情 |
| `features/watchlist/` | 自选专属 toolbar 段、中部布局、预设与上下文条 |
| `watchlist/*` | Host 协议、刷新调度 |
| `watchlist_signals/` 等 | 各子域 panel / controller / worker |

自选页检测：`page._watchlist_feature is not None`（`WatchlistPageFeature` 实例）。

---

## 5. 上下文条交互

`WatchlistPoolContextBar` 展示：`自选 · 信号 · 持仓` 用量。

| 点击段 | 行为 |
|--------|------|
| 自选 | 分组 Tab → 全量 |
| 信号 | 预设 → 盘中 |
| 持仓 | **持仓专注**（主表最小化） |

---

## 6. 测试

| 文件 | 覆盖 |
|------|------|
| `tests/ashare/ui/test_watchlist_host.py` | Host 协议字段 |
| `tests/ashare/ui/test_watchlist_context_bar.py` | 预设规格、splitter 比例、持仓专注 |
| `tests/ashare/ui/test_watchlist_toolbar.py` | toolbar policy |
| `tests/ashare/ui/test_watchlist_refresh_scheduler.py` | 单 Timer 刷新 |
