# 雷达页说明

> **定位**：盘中/盘后**盘面扫描**与**共振选股**入口；极致短线龙头能力见 [雷达选龙头](./radar-leader-screening.md)。  
> 代码：`ui/quotes/radar/` + `page_shell.RadarPageWidget`；数据：`quotes/radar/`。

---

## 1. 页面结构

```text
┌─ 工具栏：刷新 / 自动刷新 / 共振总览 / 问 AI ─────────────┐
├─ 盘面统计（statistical）— 3 列网格 ────────────────────────┤
│  选股·最新 │ 选股·任务 │ 发现·放量 │ 发现·资金 │ 自选·异动 │ 板块·主线 │
├─ 前瞻展望（predictive）— 3 列网格 ──────────────────────────┤
│  未来·关注 │ 未来·可持 │ 未来·情景 │ 未来·预测              │
└─ 共振侧栏 / 底部：跨卡加权 Top N ────────────────────────────┘
```

布局常量：`RADAR_GRID_COLUMNS = 3`（`radar_catalog.py`）。

---

## 2. 现有十卡（Phase 0）

| card_id | 标题 | 类别 | 模式 | 自动刷新 | variant |
|---------|------|------|------|----------|---------|
| `screen_latest` | 选股结果·最新 | screen | 统计 | 手动 | — |
| `screen_task` | 选股结果·任务 | screen | 统计 | 手动 | 盘中 / 盘后 / 条件选股 |
| `discovery_volume_surge` | 发现·放量异动 | discovery | 统计 | 60s | — |
| `discovery_moneyflow_intraday` | 发现·资金异动 | discovery | 统计 | 60s | — |
| `watchlist_intraday` | 自选·异动 | watchlist | 统计 | 60s | — |
| `sector_theme` | 板块·主线 | sector | 统计 | 180s | 板块龙头 / 广度扩散 |
| `outlook_watch` | 未来·关注 | outlook | 前瞻 | 手动 | — |
| `outlook_hold` | 未来·可持 | outlook | 前瞻 | 手动 | — |
| `outlook_scenario` | 未来·情景 | outlook | 前瞻 | 手动 | 偏多 / 高波动 / 偏空 |
| `outlook_predict` | 未来·预测 | outlook | 前瞻 | 手动 | auto / baseline（统计基线） |

**loader 入口**：`load_radar_board()` → 各 `load_*`（`radar_loaders.py`）。

---

## 3. 卡片职责（短线视角）

| 卡 | 极致短线用途 | 备注 |
|----|--------------|------|
| 选股·最新 / 任务 | 定时 Recipe / 条件选股结果上屏 | Hub 左侧收件箱同源 |
| 发现·放量 / 资金 | 盘中异动候选 | 交易时段 Redis 驱动 |
| 自选·异动 | 持仓 + 自选池异动 | 与信号区互补 |
| 板块·主线 | 题材 / 行业动量 | 跳转板块资金页 |
| 未来·* | 波段 / 中线辅助 | **非**打板主池；声明非确定性 |
| 共振总览 | 多卡加权 Top N | Hub「雷达共振」快捷选股数据源 |

---

## 4. 共振机制

```text
各卡 RadarRow
      │
      ▼
resonance 加权（权重可配置；D-03「短线龙头」预设 **已有**）
      │
      ▼
共振列表 → context_store → Hub screen_by_radar_resonance
                          → AI build_radar_ai_prompt
```

| 项 | 说明 | 状态 |
|----|------|------|
| 权重预设 | 默认均衡；一键「短线龙头」提高 `sector_theme`、`discovery_*`、`leader_pick` | **已有**（`radar_resonance_prefs.apply_short_term_radar_resonance_weights`） |
| 情绪 gate | T-03 退潮/冰点降权或空列表提示 | **已有** |
| 加自选 | 雷达/共振一键写入自选池（D-04） | **已有** |

---

## 5. 龙头与发现卡（Phase 1–2，**已有**）

与 [radar-leader-screening.md](./radar-leader-screening.md) 对齐：

| card_id | 标题 | ID | 状态 |
|---------|------|-----|------|
| `leader_pick` | 选股·龙头 | G-04, G-05 | **已有** |
| `discovery_limit_ladder` | 发现·连板梯队 | D-01 | **已有** |
| `discovery_first_board` | 发现·首板人气 | D-02 | **已有** |

`sector_theme` variant **leaders_tiered** 按板块展示龙一 / 龙二 / 跟风（G-02 **已有**）。

---

## 6. 行数据 RadarRow

| 字段 | 说明 |
|------|------|
| vt_symbol, name | 标的 |
| change_pct, amount | 涨跌、成交额 |
| industry, concepts | 行业 / 概念 |
| score, reasons | 卡内得分与原因 |
| `limit_times` | 连板数（G-06 **已有**） |
| `leader_tier` | 龙一 / 龙二 / 跟风（G-06 **已有**） |
| `leader_score` | 龙头分（G-06 **已有**） |
| `board_quality` | 封板质量代理 | **可选增强**（尚未落字段） |

---

## 7. UI 交互

| 操作 | 行为 |
|------|------|
| 单击行 | 跳转看盘页选中标的 |
| 卡 footer | 刷新本卡、跳转 Hub 条件选股、板块资金 |
| 问 AI | `build_radar_ai_prompt`；注入 T-03 情绪阶段（**已有**） |
| 自动刷新 | discovery / watchlist / sector 可配置间隔；screen / outlook 仅手动或读缓存 |

---

## 8. 与选股 Hub

| Hub 快捷 | 依赖 |
|----------|------|
| 雷达共振 | 本页刷新后 resonance 列表非空 |
| 雷达龙头 | `leader_pick` 卡刷新 + `run_leader_screen`（G-05） |

详见 [选股 Hub 使用指南](./screener-hub-guide.md)。

---

## 9. 与板块资金页

| 页 | 视角 |
|----|------|
| **雷达** | 短线候选：动量、共振、连板地位 |
| **板块资金** | 资金验证：主力净流入、行业排行 |

双向跳转：雷达 footer → 带 `sector_names`；板块详情 → 定位 `sector_theme`。

---

## 10. 数据依赖

| 数据 | 来源 | 卡 |
|------|------|-----|
| 实时快照 | Redis（行情采集 Job） | discovery, watchlist, sector |
| 选股 run | `screener_runs` | screen_* |
| 日 K / 模型 | 本地 bar_store | outlook_* |
| 连板 / 涨停 | Tushare `limit_list_d` + 雷达 D-01 / G-* | leader_*, D-01 |
| 市场页连板筛选 | 市场页 `limit_up` 排行 | **可选增强**（按 `limit_times` 分层筛选尚未实现） |

---

## 11. 相关文档

| 文档 | 内容 |
|------|------|
| [雷达选龙头](./radar-leader-screening.md) | leader_score、run_leader_screen |
| [交易体系 §3.4](./trading-system.md) | D-01–D-04 |
| [盘中工作流](./intraday-workflow.md) | 盘中刷新节奏 |
| [架构说明 §板块资金与雷达](./architecture.md#板块资金与雷达) | 包路径 |
| [implementation-roadmap.md](./implementation-roadmap.md) | D-/G- ID 状态 |
