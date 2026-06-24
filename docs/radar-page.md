# 雷达页

> 盘面扫描与共振选股。龙头能力见 [雷达选龙头](./radar-leader-screening.md)。  
> 代码：`ui/quotes/radar/`；数据：`quotes/radar/`。

---

## 1. 布局

```text
工具栏：刷新 / 自动刷新 / 共振总览 / 问 AI
盘面统计（3 列）：选股·最新/任务、发现卡、自选卡、板块·主线、持仓·风控…
前瞻展望（3 列）：未来·关注/可持/情景/预测
共振侧栏：跨卡加权 Top N
```

`RADAR_GRID_COLUMNS = 3`（`radar_catalog.py`）。

---

## 2. 卡片一览

| card_id | 标题 | 刷新 | 备注 |
|---------|------|------|------|
| `market_emotion` | 盘面·环境 | 60s | 不参与共振 |
| `leader_pick` | 选股·龙头 | 手动 | mainline / all_market |
| `discovery_limit_ladder` | 发现·连板梯队 | 60s | by_height / by_sector |
| `discovery_limit_break` | 发现·炸板断板 | 60s | 风险条 |
| `discovery_volume_surge` | 发现·放量异动 | 60s | |
| `discovery_moneyflow_intraday` | 发现·资金异动 | 60s | |
| `sector_flow_hot` | 板块·资金热度 | 180s | |
| `sector_theme` | 板块·主线 | 180s | leaders_tiered / breadth |
| `watchlist_short_term` | 自选·短线关注 | 60s | |
| `watchlist_intraday` | 自选·异动 | 60s | |
| `position_risk` | 持仓·风控 | 60s | |
| `outlook_*` | 未来·* | 手动 | 波段辅助，非打板主池 |

加载：`load_radar_board()` → `radar_loaders.py`。

---

## 3. 共振

各卡 `RadarRow` → 可配置权重 → 共振列表 → Hub「雷达共振」/ AI prompt。

- 预设「短线龙头」：提高 `leader_pick`、`discovery_*`、`sector_theme` 权重
- 退潮/冰点：降权或空列表提示
- 一键加自选

---

## 4. RadarRow 字段

`vt_symbol`、`change_pct`、`amount`、`industry`、`score`；龙头相关：`limit_times`、`leader_tier`、`leader_score`、`board_quality`。

单击行 → 看盘页选中；卡 footer → 刷新、Hub、板块资金；问 AI → `build_radar_ai_prompt`（含情绪阶段）。

---

## 5. 与选股 Hub

| 快捷 | 依赖 |
|------|------|
| 雷达共振 | 本页刷新后共振列表非空 |
| 雷达龙头 | `leader_pick` 刷新 + `run_leader_screen` |

---

## 6. 与板块资金

| 方向 | 入口 |
|------|------|
| 雷达 → 板块资金 | 卡片 footer |
| 板块资金 → 雷达 | 详情「雷达·龙头 / 雷达·主线」 |
| 板块资金 → 选股 | 「龙头选股」→ Hub |

---

## 7. 数据依赖

Redis 快照（discovery/watchlist/sector）、`screener_runs`（选股卡）、本地 K 线（outlook）、Tushare `limit_list_d`（连板）。

---

## 参考

[雷达选龙头](./radar-leader-screening.md) · [盘中工作流](./intraday-workflow.md) · [架构说明](./architecture.md)
