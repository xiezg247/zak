# 雷达页选股深化：选龙头股

> **阶段**：框架期需求文档。在现有雷达多卡扫描基础上，深化**人气龙头识别**与**一键选股**能力，服务 [交易体系](./trading-system.md) 中「极致短线 · 只做有辨识度人气股」原则。
>
> 技术基线见 [架构说明 §雷达](./architecture.md#板块资金与雷达)、[盘中选股](./intraday-screening.md)。

---

## 1. 功能概述

### 1.1 目标

雷达页从「盘面扫描 + 共振汇总」升级为**短线选股工作台**，新增 **选龙头股** 能力：

| 目标 | 说明 |
|------|------|
| **识别** | 在全市场 / 主线板块内，按可量化规则给出龙一、龙二、跟风梯队 |
| **展示** | 独立卡片 + 板块内分层列表；行内展示连板、封板质量、板块地位 |
| **选股** | 一键运行「龙头选股」、写入选股历史、跳转选股 Hub、批量入观察组 |
| **联动** | 与共振、板块资金、市场涨停榜、情绪周期共用同一套龙头评分 |

### 1.2 用户场景

| 场景 | 行为 |
|------|------|
| 盘中抓主线 | 打开雷达 → 「板块·主线」看强势行业 → 「选龙头」取各板块龙一 |
| 连板梯队跟踪 | 「发现·连板梯队」按 5 板 / 3 板 / 2 板 / 首板分层 |
| 共振确认 | 龙头卡 ∩ 发现卡 ∩ 选股卡 ≥ 2 → 共振列表加权上浮 |
| 退潮回避 | 情绪周期为退潮/冰点时，龙头选股结果为空或仅观察级提示 |
| 盘后复盘 | 导出当日龙头池 CSV；AI 解读「今日龙头结构 + 次日观察」 |

### 1.3 合规

- 输出为**规则排序与盘面统计**，不构成买卖建议；卡片与 AI 沿用免责声明。
- 不提供具体买入价、仓位比例指令。

---

## 2. 现状与差距

### 2.1 雷达页已有能力

```text
┌─ 盘面统计 ─────────────────────────────────────────────────┐
│ 选股结果·最新 │ 选股结果·任务 │ 发现·放量 │ 发现·资金 │ 自选·异动 │
│ 板块·主线     │                                              │
├─ 前瞻展望 ─────────────────────────────────────────────────┤
│ 未来·关注 │ 可持 │ 情景 │ 预测                                │
└────────────────────────────────────────────────────────────┘
        │                              │
        ▼                              ▼
  共振列表侧栏                   选股 Hub「雷达共振」
  （多卡交集）                   （读 radar_resonance_store）
```

| 模块 | 路径 | 职责 |
|------|------|------|
| 卡片注册 | `quotes/radar/radar_catalog.py` | 10 张卡 spec、variant、自动刷新 |
| 数据加载 | `quotes/radar/radar_loaders.py` | 统一 `load_radar_card()` |
| 板块主线 | `quotes/radar/radar_sector.py` | `sector_theme` 两 variant |
| 共振 | `radar_loaders.compute_radar_resonance` | 加权计数 + 侧栏 |
| 共振选股 | `screener/run/radar_resonance.py` | 读内存快照 → `ScreenerRunResult` |
| UI | `ui/quotes/radar/` | card、board、controller、resonance_panel |

**已有跳转**：

| 入口 | 行为 |
|------|------|
| 选股卡「查看完整」 | `open_screener_run(run_id)` |
| 板块·主线「板块资金」 | `open_sector_flow(sector_names)` |
| 共振侧栏「条件选股」 | `open_screener_radar_resonance()` |
| 共振侧栏「龙头选股」 | `open_screener_leader_screen()` |
| 行右键 / 批量 | 加自选、个股分析、AI |

### 2.2 「板块·主线」与真龙头的差距

当前 `sector_theme` 有两个 variant（`radar_catalog.SECTOR_VARIANTS`）：

| Variant | 实现 | 实际含义 | 与「龙头」差距 |
|---------|------|----------|----------------|
| **板块龙头** `leaders` | `run_sector_strength` → 强势行业内按**涨幅**排序取 Top N | 强势板块内涨最多的票 | 未区分连板高度、封板先后、资金辨识度、龙二/跟风 |
| **广度扩散** `breadth` | `breadth_leader_candidates` → 高上涨占比行业内的涨幅前列 | 扩散行情中的前排 | 偏补涨逻辑，非情绪龙头 |

板块资金页 `load_sector_leaders`（`services/sector_constituents.py`）同样按**涨幅 + 主力**排序，且仅在板块详情侧栏使用，**未接入雷达选股闭环**。

市场页已有 `limit_up`、`limit_times` 排行（`quotes/rank/rank_catalog.py`），但雷达页**未消费连板字段**。

### 2.3 需求差距汇总

| ID | 差距 | 优先级 |
|----|------|--------|
| G-01 | 无连板梯队视图 | P0 |
| G-02 | 无板块内龙一 / 龙二 / 跟风分层 | P0 |
| G-03 | 无首板人气（封板早晚、封单代理） | P1 |
| G-04 | 无统一龙头评分 `leader_score` | P0 |
| G-05 | 无「龙头选股」运行入口（仅共振选股） | P0 |
| G-06 | `RadarRow` 无连板 / 板块地位 / 龙头标签字段 | P0 |
| G-07 | 概念板块龙头未与行业龙头统一 scoring | P1 |
| G-08 | 情绪周期未 gate 龙头选股 | P1 |

---

## 3. 龙头股定义（产品规则）

### 3.1 语境

适配 A 股**极致短线**（见 [交易体系 §3](./trading-system.md#三选股体系只做有辨识度的人气股)）：

- 龙头 = 题材 / 板块内**资金共识最高、辨识度最强**的前排票，而非单纯涨幅最高。
- 只做**主流题材**内龙头；冷门补涨不算龙头池输出。

### 3.2 分层标签

| 标签 | 代号 | 判定要点（可量化） |
|------|------|-------------------|
| **龙一** | `dragon_1` | 板块内综合分最高；通常连板最高或首板最早 + 封单/成交额领先 |
| **龙二** | `dragon_2` | 同板块内 second score；常为首板次早或 1 板低于龙一 |
| **跟风** | `follower` | 同板块涨停或涨幅 ≥ 7%，但 score 明显低于龙二 |
| **杂毛** | — | **不进入龙头池**；ST、成交额 < 5000 万、非主线板块 |

### 3.3 10cm vs 20cm

| 板块 | 龙头池范围 | 备注 |
|------|------------|------|
| 沪深主板 | 优先 | 隔日打板 / 半路主战场 |
| 创业板 / 科创板 | 独立子池或标签 `cm20` | 弹性博弈；UI 区分 20cm 阈值 |
| 北交所 | 默认排除 | 硬过滤可开 |

### 3.4 主线板块判定

复用并扩展现有逻辑：

```text
load_screening_quote_snapshot()
        │
        ▼
attach_industry / 概念映射
        │
        ▼
compute_sector_distribution()  ──► 强势行业 Top 5（动量）
        │
        ├─► 叠加 sector_flow 主力净流入 Top 概念（可选）
        └─► sentiment_gate 低分时减少板块数
```

仅在这些**主线板块**内评选龙头；非主线板块的涨停票不出现在「选龙头」默认结果中（可在 variant「全市场龙头」中查看）。

---

## 4. 龙头评分引擎

### 4.1 设计原则

- **纯规则、可复现**；每个分项有明确数据来源。
- 分项缺失时降级，不阻塞整卡加载（行内 `warnings` 提示）。
- 评分结果写入 `RadarRow` 扩展字段，供共振加权与选股导出。

### 4.2 评分公式（草案）

```text
leader_score =
    w1 × norm(limit_times)           # 连板高度（0 板按首板处理）
  + w2 × norm(seal_quality)          # 封板质量代理
  + w3 × norm(amount_rank_in_sector) # 板块内成交额分位
  + w4 × norm(seal_time_score)       # 封板时间（越早越高，仅涨停）
  + w5 × norm(net_mf_amount)         # 主力净流入
  + w6 × sector_strength_bonus       # 所属板块是否为当日主线
  + w7 × resonance_bonus             # 是否出现在其他雷达卡（加载后二次 pass）
```

**默认权重（可 QSettings 配置）**：

| 分项 | 权重 | 说明 |
|------|------|------|
| 连板 | 0.28 | Redis `limit_times`；Tushare `limit_list_d` 盘后补全 |
| 封板质量 | 0.18 | 见 §4.3 |
| 成交额 | 0.15 | 板块内 rank |
| 封板时间 | 0.12 | 见 §4.4 |
| 主力 | 0.12 | `net_mf_amount` 或 Tushare moneyflow |
| 主线加成 | 0.10 | 行业在 `distribution` Top 5 内 |
| 共振加成 | 0.05 | 二次计算 |

### 4.3 封板质量代理 `seal_quality`

| 信号 | 分值 | 数据 |
|------|------|------|
| 换手 5%–25% 且涨停 | 高 | `turnover_rate` + 涨停判定 |
| 一字板（开盘即涨停且振幅极小） | **低（打板回避）** | 分 K / 振幅 |
| 炸板后回封 | 中–高 | `limit_list_d.open_times` + 分 K 状态机（**已有**） |
| 非涨停强势 | 按涨幅线性 | 半路模式 |

Phase 1 可简化为：**涨停 + 非近似一字 + 成交额分位**。

### 4.4 封板时间 `seal_time_score`

| 时段 | 得分 |
|------|------|
| 09:25–10:30 封板 | 1.0 |
| 10:30–13:30 | 0.7 |
| 13:30–15:00 | 0.5 |
| 非涨停 | 0 |

数据源优先级：TickFlow 分 K 首次触及涨停价时间 → Tushare `limit_list_d.first_time`（盘后）→ 缺失则不计分项。

### 4.5 板块内排序与标签分配

```python
# quotes/radar/radar_leader.py（规划）

def rank_sector_leaders(
    candidates: list[dict],
    *,
    sector_key: str,
) -> list[LeaderRankedRow]:
    """同板块内降序；Top1=dragon_1, Top2=dragon_2, 其余涨停/强势=follower。"""
```

- 每板块最多输出 **2 龙 + 3 跟风**（可配置），避免单板块占满整卡。
- 全市场汇总后再按 `leader_score` 取 Top N 展示。

### 4.6 模块结构（规划）

```text
quotes/radar/
├── radar_leader.py          # 评分、分层、标签
├── radar_leader_pool.py     # 候选池构建（涨停+强势+板块过滤）
├── radar_limit_ladder.py    # 连板梯队 loader
├── radar_first_board.py     # 首板人气 loader
└── radar_sector.py          # 扩展 sector_theme，调用 radar_leader
```

---

## 5. 卡片与 UI 设计

### 5.1 新增 / 改造卡片

| card_id | 标题 | 类别 | 说明 |
|---------|------|------|------|
| `discovery_limit_ladder` | 发现·连板梯队 | discovery | 按 `limit_times` 分 Tab 或分段：≥5 / 4 / 3 / 2 / 首板 |
| `discovery_first_board` | 发现·首板人气 | discovery | 当日首板（`limit_times=1`）按 seal_time + amount 排序 |
| `leader_pick` | **选股·龙头** | **screen** | **主入口**：主线板块龙一 + 龙二 + 评分 |
| `sector_theme` | 板块·主线 | sector | **改造** variant「板块龙头」→ 真龙一分层；新增 variant「龙二跟风」 |

**注册表示例扩展**（`radar_catalog.py`）：

```python
RadarCardSpec("discovery_limit_ladder", "发现·连板梯队", "discovery", auto_refresh_ms=60_000)
RadarCardSpec("discovery_first_board", "发现·首板人气", "discovery", auto_refresh_ms=60_000)
RadarCardSpec("leader_pick", "选股·龙头", "screen", top_n=12)
```

**Variant 扩展**：

| 卡片 | 新 variant | 说明 |
|------|------------|------|
| `leader_pick` | `mainline` / `all_market` / `cm20_only` | 默认 `mainline` 仅主线龙一 |
| `sector_theme` | `leaders_tiered` / `breadth` | 替代原 `leaders`；`leaders_tiered` 按板块分组展示 |
| `discovery_limit_ladder` | `by_height` / `by_sector` | 按高度 vs 按板块聚合 |

### 5.2 RadarRow 扩展字段

| 字段 | 类型 | 展示 |
|------|------|------|
| `leader_score` | float | 副指标「龙头分」 |
| `leader_tier` | `dragon_1 \| dragon_2 \| follower \| ""` | 角标 / 标签色 |
| `limit_times` | int | 连板数 |
| `sector_name` | str | 行业或概念 |
| `seal_time_label` | str | 如「10:12 封板」 |
| `board_tag` | `10cm \| 20cm` | 板块标签 |

现有 `metric_label / metric_value / sub_label / sub_value` 保留；连板优先占 `metric_*`，龙头分占 `sub_*`。

**行角标**（`row_widget.py`）：

```text
[龙一]  贵州茅台  +10.01%   3连板   龙头分 87.2
[龙二]  …
[跟风]  …
```

### 5.3 页面布局

```text
┌─ 雷达顶栏 ─────────────────────────────────────────────────────────┐
│ [刷新全部]  情绪：发酵期·建议仓位50%  │  [选龙头▾] [龙头选股→Hub]   │
├─ 卡片网格（3 列）────────────────────┬─ 共振列表 ─────────────────┤
│  … 发现·连板梯队  发现·首板人气 …     │  [全部加自选] [AI解读]       │
│  … 选股·龙头      板块·主线 …         │  [龙头选股] [条件选股]       │
└──────────────────────────────────────┴────────────────────────────┘
```

**顶栏「选龙头」**：下拉快捷 variant（主线龙一 / 连板梯队 / 首板人气），切换时 scroll 到对应卡并刷新。

**「龙头选股→Hub」**：执行 `run_leader_screen()`，带当前 variant 与 hard filter，打开选股 Hub 结果 Tab。

### 5.4 卡片 footer 动作

| 卡片 | 新增按钮 | 行为 |
|------|----------|------|
| `leader_pick` | **龙头选股** | 当前卡 Top N → `ScreenerRunResult` |
| `leader_pick` | **加观察组** | 写入 watchlist_groups「短线观察」 |
| `discovery_limit_ladder` | 按层加自选 | 选中 Tab 内全部 |
| `sector_theme` | 板块资金 | 已有；预选当前卡 `sector_names` |

### 5.5 共振侧栏扩展

| 现有 | 新增 |
|------|------|
| 条件选股（雷达共振） | **龙头选股**按钮 |
| 全部加自选 | **龙一加观察组**（仅 `leader_tier=dragon_1`） |
| 权重配置 | 预设「短线龙头」：提高 `leader_pick`、`discovery_limit_ladder` 权重 |

**共振加权**（`radar_resonance_prefs.py`）新增项：

```python
"leader_pick": 2.5,
"discovery_limit_ladder": 2.0,
"discovery_first_board": 1.75,
```

出现在「选股·龙头」+「连板梯队」+「板块·主线」的标的，共振分显著高于仅出现在单卡者。

---

## 6. 选股执行与数据流

### 6.1 龙头选股 vs 雷达共振

| 维度 | 雷达共振（已有） | 龙头选股（新增） |
|------|------------------|------------------|
| 输入 | 共振侧栏内存快照 | `leader_pick` 卡 或 连板梯队 或 用户勾选 |
| 排序 | `resonance_score` | `leader_score` |
| 过滤 | 无 | 硬过滤 + 主线板块 gate + 情绪周期 gate |
| 输出字段 | `card_count`, `hit_reason` | `leader_tier`, `limit_times`, `sector_name` |
| trigger | `radar` | `radar_leader` |

### 6.2 执行路径

```text
用户点击「龙头选股」
        │
        ▼
LeaderScreenWorker (QThread)
        │
        ├─► load_leader_pick_card(force_recompute=True)
        ├─► apply_screening_filters(hard_filter_prefs)
        ├─► emotion_cycle_gate (可选，退潮→空结果+提示)
        │
        ▼
run_leader_screen(top_n, variant) → ScreenerRunResult
        │
        ├─► persist_run_result(trigger="radar_leader")
        ├─► context_store 注入
        └─► open_screener_run /  Hub 内嵌结果
```

**新增文件**：

```text
screener/run/radar_leader.py      # run_leader_screen()
ui/screener/workers/              # LeaderScreenWorker
```

### 6.3 与选股 Hub 集成

| 入口 | 位置 |
|------|------|
| 条件选股 · 快捷选股 | 新增「龙头选股」；说明需先刷新雷达 |
| 多因子配方 · 工具栏 | 「雷达龙头」按钮（与「雷达共振」并列） |
| 运行历史 | `[雷达龙头]` tag；`trigger=radar_leader` |

结果表新增列（有则显示）：

| 列 | 说明 |
|----|------|
| 龙头分 | `leader_score` |
| 地位 | 龙一 / 龙二 / 跟风 |
| 连板 | `limit_times` |
| 板块 | `sector_name` |
| 命中原因 | 规则文案 |

导出 CSV 走 `resolve_export_columns` 自动推断「龙头列集」。

---

## 7. 数据依赖

| 数据 | 来源 | 用途 | 降级 |
|------|------|------|------|
| 全市场行情 | Redis + `load_screening_quote_snapshot` | 涨幅、成交额、换手 | 提示采集 Job |
| `limit_times` | Redis 排行字段 | 连板梯队 | Tushare 盘后 |
| 涨停列表 | `limit_list_d` | 封板时间、开板次数 | 近似涨停 filter |
| 行业映射 | Tushare `stock_industry` | 板块分组 | 跳过无行业 |
| 概念成分 | `fetch_ths_member_vt_symbols` | 概念龙头 | 仅行业模式 |
| 主力净流入 | Redis / Tushare moneyflow | 评分分项 | 权重归零 |
| 分 K | TickFlow | 封板时间、一字判定 | 不计 seal_time |
| 板块资金 | `SectorFlowService` | 主线概念交叉验证 | 可选 |

**刷新策略**：

| 卡片 | 自动刷新 | 全量重算 |
|------|----------|----------|
| 连板梯队 | 60s | 每 5 tick |
| 首板人气 | 60s | 每 5 tick |
| 选股·龙头 | 手动 + 随顶栏刷新 | 每次 |
| 板块·主线 | 180s（已有） | 权重变更时 |

---

## 8. 情绪周期与硬过滤

联动 [交易体系 §2](./trading-system.md#二择时体系情绪周期决定做不做)（`emotion_cycle` **已有**）：

| 情绪阶段 | 龙头选股行为 |
|----------|--------------|
| 冰点 / 退潮 | 结果为空或仅展示「观察」级；UI 横幅「当前不宜做龙头」 |
| 启动 | 默认 `discovery_first_board` + 龙一 Top 5 |
| 发酵 / 高潮 | 默认 `leader_pick` mainline + 连板梯队 |
| 分歧 | 仅龙一 + 低吸标签提示；过滤跟风 |

**硬过滤默认（龙头激进模板）**：

| 规则 | 值 |
|------|-----|
| 排除 ST / 停牌 | 是 |
| 最低成交额 | 5000 万 |
| 流通市值 | 30–200 亿（10cm）；20–150 亿（20cm） |
| 排除一字板 | 可选，默认开 |
| 仅主线板块 | `leader_pick` mainline variant 默认开 |

---

## 9. AI 能力

### 9.1 预填 Prompt 扩展

| 入口 | 函数 | 内容 |
|------|------|------|
| 整页 AI | `build_radar_ai_prompt` | 增加「选股·龙头」卡 + 连板梯队摘要 |
| 共振 AI | `build_radar_resonance_ai_prompt` | 标注龙一 / 共振交集 |
| 龙头卡 AI | `build_leader_pick_ai_prompt`（新） | 板块龙结构 + 次日 3–5 只观察 |

**示例输出要求**（写入 prompt）：

1. 今日主线板块与龙一 / 龙二关系  
2. 连板高度与市场情绪是否匹配  
3. 不宜追高的标的（一字、异动预警）  
4. 不编造未出现在卡片中的价格  

### 9.2 新增工具（规划）

| 工具 | Skill | 说明 |
|------|-------|------|
| `get_leader_pick_snapshot` | vnpy-screening | 返回当前龙头池 JSON |
| `run_leader_screen` | vnpy-screening | 执行龙头选股并落库 |
| `explain_leader_tier` | vnpy-analysis | 解读单票为何为龙一 / 龙二 |

### 9.3 路由短语

| 用户表述 | 优先工具 |
|----------|----------|
| 今天龙头 / 龙一 / 连板梯队 | `get_leader_pick_snapshot` |
| 帮我选龙头 / 龙头选股 | `run_leader_screen` |
| 为什么 XX 是龙头 | `explain_leader_tier` + `get_quote_context` |

---

## 10. 测试要点

| 文件 | 覆盖 |
|------|------|
| `tests/ashare/quotes/test_radar_leader.py` | 评分、分层、同板块龙一龙二 |
| `tests/ashare/quotes/test_radar_limit_ladder.py` | 梯队分组、空池 |
| `tests/ashare/screener/test_radar_leader_screen.py` | `run_leader_screen`、硬过滤、空共振 |
| `tests/ashare/ui/test_radar_leader_ui.py` | 卡片 variant、footer 按钮 |
| 扩展 `test_radar_resonance.py` | 龙头卡纳入共振加权 |

**Fixture 建议**：构造含 `limit_times`、多行业、同板块多涨停的 snapshot rows。

---

## 11. 实施分期

### Phase 1 — 龙头评分 + 主卡（MVP）

- [x] `radar_leader.py` 评分与 `leader_tier` 分配
- [x] 新卡 `leader_pick`（variant `mainline`）
- [x] `RadarRow` 扩展 + 行 UI 角标
- [x] `run_leader_screen` + Hub「雷达龙头」按钮
- [x] 共振权重预设

### Phase 2 — 发现卡 + 板块改造

- [x] `discovery_limit_ladder`  
- [x] `discovery_first_board`  
- [x] `sector_theme` → `leaders_tiered`  
- [x] 封板时间 / 封单强度（`limit_list_d` + 首板维度）  

### Phase 3 — 联动与 gate

- [x] 情绪周期 gate（`sentiment_gate` / `emotion_modulation`）  
- [x] watchlist_groups「短线观察」一键写入  
- [x] AI prompt + Skill 工具（`run_leader_screen` 等）  
- [x] 顶栏「选龙头」快捷导航（`radar_leader_button` → `focus_card` + Hub）  

### Phase 4 — 深化

- [x] 概念 + 行业双主线统一池（`rank_unified_sector_leaders`）  
- [x] 炸板回封检测（`seal_reopen` + `open_times`）  
- [x] 异动监管距离（概览 Tab + `assess_regulatory_deviation`；龙头列表 `regulatory_hint` 列）  
- [x] 龙头选股回测 batch 入口（Hub「批量回测」+ `trigger=radar_leader` → 极致短线打板模板）  

---

## 12. 相关文档

| 文档 | 关联 |
|------|------|
| [交易体系需求](./trading-system.md) | 短线选股原则、情绪周期、Recipe R-01 |
| [盘中选股](./intraday-screening.md) | 硬过滤、Recipe 框架 |
| [选股 Hub 使用指南](./screener-hub-guide.md) | 雷达共振操作（将并列增加雷达龙头） |
| [雷达页](./radar-page.md) | 十卡与共振总览 |
| [implementation-roadmap.md](./implementation-roadmap.md) | G-/D- ID 状态 |
| [产品说明](./product-plan.md) | 雷达页导航 |
| [AI 数据路由](./ai-data-routing.md) | Skill 注册 |

---

## 附录 A：与板块资金页的分工

| 页 | 视角 | 龙头能力 |
|----|------|----------|
| **板块资金** | 行业 / 概念 **资金**维度 | 详情侧栏成分龙头（涨幅+主力）；偏资金验证 |
| **雷达** | **短线选股**维度 | 连板 + 封板质量 + 板块地位 + 共振；偏交易候选 |

跳转保持双向：雷达「板块资金」→ 带 `sector_names`；板块详情「在雷达中查看」→ 定位 `sector_theme` / `leader_pick` 过滤该板块。

## 附录 B：名词表

| 名词 | 含义 |
|------|------|
| 龙一 / 龙二 | 板块内 leader_score 第 1 / 第 2，且有明显辨识度 |
| 跟风 | 同板块强势但非核心 |
| 杂毛 | 非主流、低辨识度；不进池 |
| 首板 | `limit_times = 1` 且当日首次涨停 |
| 主线 | 当日动量或资金 Top 行业 / 概念 |
| 封板质量 | 换手、一字、回封等综合代理，非 L2 封单 |
