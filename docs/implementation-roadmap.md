# 实施路线图（需求 ID 总表）

> **用途**：跨文档统一追踪「极致短线为主」框架期需求的状态、依赖与分期。  
> 总纲见 [交易体系需求](./trading-system.md)；日路径见 [盘中工作流](./intraday-workflow.md)。

---

## 1. 状态图例

| 状态 | 含义 |
|------|------|
| **已有** | 代码可用，文档与实现一致 |
| **部分** | 核心能力存在，短线扩展未完成 |
| **待建** | 仅 spec，无实现 |
| **不做** | 产品明确排除，不实现 |
| **规划** | Phase 4+ 或可选增强 |

---

## 2. 择时（T-）

| ID | 能力 | 状态 | Phase | 依赖 | 落点 / 文档 |
|----|------|------|-------|------|-------------|
| T-01 | 市场广度条 | **已有** | 0 | Redis / TickFlow | 市场页；[market-page.md](./market-page.md) |
| T-02 | 恐贪 + 北向环境 | **已有** | 0 | Tushare | `market_environment` |
| T-03 | 情绪周期引擎 | **已有** | 1 | T-01, 连板 | `emotion_cycle.py`；[emotion-cycle.md](./emotion-cycle.md) |
| T-04 | 择时闸 UI 芯片 | **已有** | 1 | T-03 | 市场页 stats_bar |
| T-05 | sentiment_gate × 周期系数 | **已有** | 1 | T-03 | `screener/sentiment/sentiment_gate` |
| T-06 | 退潮期批量入自选软拦截 | **已有** | 1 | T-03 | 选股 `ScreenerResultActionBar` |

---

## 3. 选股 Recipe（R-）

| ID | 名称 | 状态 | Phase | 依赖 | 文档 |
|----|------|------|-------|------|------|
| R-01 | `ultra_short_limit` | **已有** | 1 | 硬过滤激进模板、G-04 | [intraday-screening.md](./intraday-screening.md) |
| R-02 | `ultra_short_first_board` | **已有** | 2 | D-02, 封板代理 | 同上 |
| R-03 | `cm20_elastic` | **已有** | 2 | 板块白名单 | 同上 |
| R-04 | `emotion_gate_only` | **已有** | 1 | T-03 | [emotion-cycle.md](./emotion-cycle.md) |
| — | `ultra_short_unified`（极致短线·雷达统一） | **已有** | 3 | D-03 leader_score、D-04 radar_resonance、R-01 | [intraday-screening.md](./intraday-screening.md) |
| — | `intraday_multi`（默认盘中） | **已有** | 0 | Redis | [intraday-screening.md](./intraday-screening.md) |

**硬过滤**：保守 / 均衡 / 激进三模板；激进模板 Phase 1 与 R-01 同批交付。

---

## 4. 雷达（D- / G-）

### 4.1 卡片与共振（D-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| D-01 | `discovery_limit_ladder` 连板梯队 | **已有** | 2 | [radar-page.md](./radar-page.md) |
| D-02 | `discovery_first_board` 首板人气 | **已有** | 2 | 同上 |
| D-03 | 共振权重「短线模式」 | **已有** | 1 | [radar-leader-screening.md](./radar-leader-screening.md) |
| D-04 | 共振 → 自选池 | **已有** | 1 | [watchlist-groups.md](./watchlist-groups.md) |
| D-05 | `market_emotion` 盘面·环境 | **已有** | A+B | [radar-page.md](./radar-page.md) |
| D-06 | `discovery_limit_break` 炸板断板 | **已有** | A+B | 同上 |
| D-07 | `watchlist_short_term` 短线关注 | **已有** | A+B | 同上 |
| D-08 | `sector_flow_hot` 板块资金热度 | **已有** | A+B | 同上 |
| — | 现有卡片 + 共振总览 | **已有** | 0 | [radar-page.md](./radar-page.md) |

### 4.2 龙头专项（G-）

| ID | 差距 | 优先级 | Phase | 状态 |
|----|------|--------|-------|------|
| G-01 | 连板梯队视图 | P0 | 2 | **已有** |
| G-02 | 龙一 / 龙二 / 跟风 | P0 | 1 | **已有** |
| G-03 | 首板人气 | P1 | 2 | **已有** |
| G-04 | `leader_score` | P0 | 1 | **已有**（评分+板块/龙头卡+选股输出） |
| G-05 | `run_leader_screen` Hub 入口 | P0 | 1 | **已有** |
| G-06 | `RadarRow` 扩展字段 | P0 | 1 | **已有**（tier 角标+metric/sub 展示） |
| G-07 | 概念 + 行业统一 scoring | P1 | 4 | **已有** |
| G-08 | 情绪 gate 龙头选股 | P1 | 1 | **已有**（`run_leader_screen` 退潮/冰点空池） |

---

## 5. 策略与买卖点（S- / SP-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| S-01 | 短线策略族注册 | **已有** | 2 | [strategy-profiles.md](./strategy-profiles.md) |
| S-02 | 信号区 Profile 切换 | **已有** | 1 | 同上 |
| S-03 | 持仓退出规则集 | **已有** | 2 | ultra_short OvernightExit overlay |
| S-04 | 分 K 买卖参考线 | **已有** | 2 | 分 K Tab 叠加参考线 |
| S-05 | 开盘 30 分钟止损提醒 | **已有** | 2 | `opening_stop` + 持仓异动 |
| SP-01 | Profile 枚举 + QSettings | **已有** | 1 | [strategy-profiles.md](./strategy-profiles.md) |
| SP-02 | 信号区 Profile 下拉 | **已有** | 1 | 同上 |
| SP-03 | 持仓区 header Profile | **已有** | 1 | 同上 |
| SP-04 | 新用户默认 Profile 配置 | **已有** | 1 | 同上 |
| SP-05 | LimitBoard / OvernightExit | **已有** | 2–5 | 日 K 打板 CTA + limit_list 封板时间 + 隔日退出 overlay |
| — | 四套现有策略（双均线等） | **已有** | 0 | `strategies/registry.py` |

---

## 6. 仓位与自选（P-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| P-01 | 持仓记账 | **已有** | 0 | [watchlist-positions.md](./watchlist-positions.md) |
| P-02 | T+1 锁定 | **已有** | 0 | 同上 |
| P-03 | 浮盈 / exit_signal | **已有** | 0 | 同上 |
| P-04 | 计划仓位 % | **已有** | 3 | 同上 |
| P-05 | 情绪仓位系数对比 | **已有** | 3 | 持仓区 stats；依赖 T-03 |
| P-06 | 自选分组 Tab | **已有** | 0 | [watchlist-groups.md](./watchlist-groups.md) |
| P-07 | 分组级仓位汇总 | **已有** | 3 | 同上 |

---

## 7. 风控（K-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| K-01 | 总资金与风控参数 | **已有** | 3 | 持仓区「风控设置」（基础 / 高级） |
| K-02 | 单笔风险计算器 | **已有** | 3 | 登记对话框 + `compute_position_size` |
| K-03 | 当日已实现 + 浮亏汇总 | **已有** | 3 | 记账浮盈 + 手动已实现 |
| K-04 | normal / caution / halt | **已有** | 3 | 顶栏芯片 + 登记 toast（不阻断） |
| K-05 | 违规 off_plan 标记 | **已有** | 4 | [trading-plan-journal.md](./trading-plan-journal.md) |

---

## 8. 复盘与计划（J-）

| ID | 能力 | 状态 | Phase | 存储 | 文档 |
|----|------|------|-------|------|------|
| J-01 | `trading_plans` 表 | **已有** | 4 | App DB | [trading-plan-journal.md](./trading-plan-journal.md) |
| J-02 | `trade_journal` 表 | **已有** | 3–4 | App DB | 同上 |
| J-03 | `propose_trading_plan` AI | **已有** | 4 | — | [ai-data-routing.md](./ai-data-routing.md) |
| J-04 | 计划内 / 计划外校验 | **已有** | 4 | J-01, P-01 | 同上 |
| J-05 | 复盘报表（胜率 / 盈亏比） | **已有** | 5 | J-02 | 同上 |
| — | 笔记流水 `stock_note_entries` | **已有** | 0 | App DB | [stock-notes.md](./stock-notes.md) |

---

## 9. 通知（N-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| N-01 | 飞书 Webhook MVP | **已有** | 1 | [notifications.md](./notifications.md) |
| N-02 | 事件白名单 + 限频 | **已有** | 1 | 同上 |
| N-03 | 定时任务 screener 完成推送 | **已有** | 1 | 同上 |
| N-04 | 情绪 / 风控状态变更推送 | **已有** | 2 | 联动 `emotion_cycle` + `risk_gate_engine` |
| N-05 | `notify_delivery_log` | **已有** | 2 | [data-design.md](./data-design.md) |
| N-06 | interactive 卡片 | **已有** | 3 | [notifications.md](./notifications.md) |

---

## 10. AI 工具（A-）

| ID | 工具 | 状态 | Phase | Skill |
|----|------|------|-------|-------|
| A-01 | `get_emotion_cycle` | **已有** | 1 | vnpy-sentiment 扩展 |
| A-02 | `get_short_term_watchlist` | **已有** | 1 | vnpy-watchlist 扩展 |
| A-03 | `propose_trading_plan` | **已有** | 4 | vnpy-trading（新） |
| A-04 | `get_trade_journal` | **已有** | 4 | 同上 |
| A-05 | `check_risk_gate` | **已有** | 3 | vnpy-trading Skill |
| A-06 | `evaluate_entry_mode` | **已有** | 2 | vnpy-analysis 扩展 |
| A-07 | `run_leader_screen` | **已有** | 1 | vnpy-screening 扩展 |
| — | 现有 Skills 清单 | **已有** | 0 | [ai-data-routing.md](./ai-data-routing.md) |

---

## 11. 历史实施顺序（Phase 1–5 已完成）

与 [trading-system.md §12](./trading-system.md#12-实施分期) 对齐；**Phase 1–5 已全部交付**（上表 §2–§10 状态均为 **已有**）。下列为归档用实施顺序，可并行项用 `‖` 标注。

```text
Phase 1 ✅
├── N-01 ‖ N-02          飞书 MVP
├── T-03 → T-04 → T-05   情绪周期链
├── G-04 → G-02 → G-05   龙头评分 + Hub 入口
├── R-01 + 激进硬过滤
├── SP-01 → SP-02        Profile 基础
├── P-06                  自选分组 Tab
└── A-01, A-07           AI 择时 + 龙头

Phase 2 ✅
├── S-01, SP-05          短线策略插件
├── D-01, D-02           发现卡
├── R-02, R-03
└── N-03, N-04

Phase 3 ✅
├── K-01 ~ K-04, P-04, P-05
└── J-02（流水）

Phase 4 ✅
├── J-01, J-03, J-04, K-05
└── 复盘 UI

Phase 5 ✅
├── 中线辅线回测验证
└── J-05 报表
```

---

## 12. 文档索引

| 域 | 主文档 |
|----|--------|
| 总纲 | [trading-system.md](./trading-system.md) |
| 日路径 | [intraday-workflow.md](./intraday-workflow.md) |
| 择时 | [emotion-cycle.md](./emotion-cycle.md) |
| 选股 | [intraday-screening.md](./intraday-screening.md)、[screener-hub-guide.md](./screener-hub-guide.md) |
| 雷达 | [radar-page.md](./radar-page.md)、[radar-leader-screening.md](./radar-leader-screening.md) |
| 自选 | [watchlist-groups.md](./watchlist-groups.md)、[watchlist-positions.md](./watchlist-positions.md)、[watchlist-signals.md](./watchlist-signals.md) |
| 策略 | [strategy-profiles.md](./strategy-profiles.md) |
| 风控 | [risk-gate.md](./risk-gate.md) |
| 复盘 | [trading-plan-journal.md](./trading-plan-journal.md) |
| 通知 | [notifications.md](./notifications.md) |
| 数据 | [data-design.md](./data-design.md) |
| AI | [ai-data-routing.md](./ai-data-routing.md) |
| 配置 | [config-hot-reload.md](./config-hot-reload.md) |
| 架构 | [architecture.md](./architecture.md) |

---

## 13. 维护约定

1. 新增需求须分配 **唯一 ID**（上表前缀 + 序号），并在对应域文档写细节。
2. 实现合并后更新本表 **状态** 列；Phase 变更须同步 [trading-system.md §12](./trading-system.md#12-实施分期)。
3. 跨 ID 依赖在 PR / 任务描述中引用（如 `T-03 blocks G-08`）。
4. Post-Phase 项写入 **§14**，不占用 T-/G- 等正式 ID。

---

## 14. Post-Phase backlog

> **用途**：Phase 1–5 交付后的精度、体验与文档债；合并 PR 时在此表增删行即可。

| 优先级 | 项 | 状态 | 落点 / 说明 |
|--------|-----|------|-------------|
| P0 | 情绪周期阈值 QSettings + 设置 UI | **已有** | 系统配置 →「情绪周期」Tab |
| P0 | 退潮判定：断板率、昨最高板跌停 | **已有** | `emotion_ladder_continuity` + 日切表 |
| P0 | 阶段边界 hysteresis | **已有** | `emotion_cycle_hysteresis` + 设置「阶段迟滞」 |
| P0 | 监管异动 Tushare 官方偏离度 | **已有** | `stk_shock` / `stk_high_shock` + 本地合并 |
| P0 | 子文档与 roadmap 状态对齐 | **已有** | 2026-06 首轮同步完成 |
| P1 | 新用户 ultra_short onboarding | **已有** | 自选页首次引导 + 盘中布局预设 |
| P1 | 选股 Hub「过滤至短线主池」 | **已有** | 结果条「短线主池」+ `ultra_short_pool_filter` |
| P1 | 盘后 AI「龙头结构 + 明日观察」 | **已有** | 雷达共振侧栏「盘后解读」+ `build_eod_leader_prompt` |
| P1 | 信号区+持仓 1m K 自动补全 | **已有** | Job `fill_focus_pool_minute`（关注池 = 信号区 ∪ 持仓）+ 分 K 回测预检 |
| P2 | 微信 / 邮件通知 | **不做** | 产品范围外；飞书已覆盖主通道，见 [notifications §1.3](./notifications.md#13-与-vnpy-内置通道关系) |
| P2 | 券商持仓 `source=gateway` | **不做** | 维持手工记账；`PositionRecord.source` 字段保留兼容 |
| P2 | 市场页涨停榜内连板分层筛选 | **不做** | 侧栏「连板榜」（`limit_times`）+ 雷达 D-01 已覆盖；见 [market-page.md](./market-page.md) §3 |
| P2 | 板块资金 ↔ 雷达/龙头闭环 | **已有** | 详情侧栏「雷达·龙头 / 雷达·主线 / 龙头选股」；`main_window.open_radar_card` |
| — | Profile 切换同步硬过滤模板 | **已有** | `apply_strategy_profile` → 保守/均衡/激进 |
| — | NL 选股 `propose_*` 执行前确认 | **已有** | `AgentGateway` + Qt 确认；系统配置 → AI 助手 |
| — | 子文档 Post-Phase 表述对齐 | **已有** | trading-system §3.2、watchlist-groups、ai-data-routing 等 |
| — | 子文档「规划」滞后同步 | **已有** | 2026-06 文档债清理：watchlist-positions、strategy-profiles、radar-page、data-design、notifications、trading-plan-journal、radar-leader-screening |

> **Post-Phase 结论（2026-06）**：P0/P1 已全部交付；P2「不做」项含微信/邮件、券商同步、市场页连板分层 Tab；续项（Profile/硬过滤、NL 确认、文档）已同步上表。
