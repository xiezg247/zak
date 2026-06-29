# 雷达页

`Ctrl+6`。盘面扫描、共振选股与 Hub 快捷入口。龙头细则见 [雷达选龙头](./radar-leader-screening.md)。代码：`ui/quotes/radar/`、`quotes/radar/`。

---

## 布局

```text
工具栏：刷新 / 自动刷新 / 共振总览 / 问 AI
盘面统计（3 列）：龙头、发现卡、自选卡、板块·主线、持仓·风控…
前瞻展望（3 列）：未来·关注/可持/情景/预测（波段辅助，非打板主池）
共振侧栏：跨卡加权 Top N → Hub「雷达共振」/ 加自选
```

`RADAR_GRID_COLUMNS = 3`。单击行联动看盘；问 AI → `build_radar_ai_prompt`（含情绪阶段）。

---

## 主要卡片

| card_id | 标题 | 刷新 |
|---------|------|------|
| `market_emotion` | 盘面·环境 | 60s（不参与共振） |
| `leader_pick` | 选股·龙头 | 手动 |
| `discovery_limit_ladder` | 发现·连板梯队 | 60s |
| `discovery_limit_break` | 发现·炸板断板 | 60s |
| `discovery_volume_surge` / `discovery_moneyflow_intraday` | 放量 / 资金异动 | 60s |
| `sector_flow_hot` / `sector_theme` | 板块资金 / 主线 | 180s |
| `watchlist_short_term` / `watchlist_intraday` | 自选·短线 / 异动 | 60s |
| `position_risk` | 持仓·风控 | 60s |
| `outlook_*` | 未来·* | 手动 |

加载：`load_radar_board()` → `radar_loaders.py`。共振预设「短线龙头」提高龙头/发现/板块权重；退潮/冰点可降权或空列表。

---

## 与 Hub / 板块资金

| 快捷 | 依赖 |
|------|------|
| 雷达共振 | 本页刷新后共振列表非空 |
| 雷达龙头 | `leader_pick` 刷新 + `run_leader_screen` |

板块资金 ↔ 雷达 footer / 详情「雷达·龙头·主线」；板块资金「龙头选股」→ Hub。数据：Redis 快照、`limit_list_d`、本地 K 线（outlook）、`screener_runs`。

---

[盘中工作流](./intraday-workflow.md) · [架构说明](./architecture.md)
