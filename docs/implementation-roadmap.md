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
| **规划** | Phase 4+ 或可选增强 |

---

## 2. 择时（T-）

| ID | 能力 | 状态 | Phase | 依赖 | 落点 / 文档 |
|----|------|------|-------|------|-------------|
| T-01 | 市场广度条 | **已有** | 0 | Redis / TickFlow | 市场页；[market-page.md](./market-page.md) |
| T-02 | 恐贪 + 北向环境 | **已有** | 0 | Tushare | `market_environment` |
| T-03 | 情绪周期引擎 | **待建** | 1 | T-01, 连板数据 | `quotes/market/emotion_cycle.py`；[emotion-cycle.md](./emotion-cycle.md) |
| T-04 | 择时闸 UI 芯片 | **待建** | 1 | T-03 | 市场页 / 自选顶栏 |
| T-05 | sentiment_gate × 周期系数 | **部分** | 1 | T-03 | `screener/dimensions/sentiment_gate` |
| T-06 | 退潮期批量入自选软拦截 | **待建** | 1 | T-03 | 选股 `ScreenerResultActionBar` |

---

## 3. 选股 Recipe（R-）

| ID | 名称 | 状态 | Phase | 依赖 | 文档 |
|----|------|------|-------|------|------|
| R-01 | `ultra_short_limit` | **待建** | 1 | 硬过滤激进模板、G-04 | [intraday-screening.md](./intraday-screening.md) |
| R-02 | `ultra_short_first_board` | **待建** | 2 | D-02, 封板代理 | 同上 |
| R-03 | `cm20_elastic` | **待建** | 2 | 板块白名单 | 同上 |
| R-04 | `emotion_gate_only` | **待建** | 1 | T-03 | [emotion-cycle.md](./emotion-cycle.md) |
| — | `intraday_multi`（默认盘中） | **已有** | 0 | Redis | [intraday-screening.md](./intraday-screening.md) |

**硬过滤**：保守 / 均衡 / 激进三模板；激进模板 Phase 1 与 R-01 同批交付。

---

## 4. 雷达（D- / G-）

### 4.1 卡片与共振（D-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| D-01 | `discovery_limit_ladder` 连板梯队 | **待建** | 2 | [radar-page.md](./radar-page.md) |
| D-02 | `discovery_first_board` 首板人气 | **待建** | 2 | 同上 |
| D-03 | 共振权重「短线模式」 | **待建** | 1 | [radar-leader-screening.md](./radar-leader-screening.md) |
| D-04 | 共振 → 短线观察组 | **待建** | 1 | [watchlist-groups.md](./watchlist-groups.md) |
| — | 现有 10 卡 + 共振总览 | **已有** | 0 | [radar-page.md](./radar-page.md) |

### 4.2 龙头专项（G-）

| ID | 差距 | 优先级 | Phase | 状态 |
|----|------|--------|-------|------|
| G-01 | 连板梯队视图 | P0 | 2 | **待建** |
| G-02 | 龙一 / 龙二 / 跟风 | P0 | 1 | **待建** |
| G-03 | 首板人气 | P1 | 2 | **待建** |
| G-04 | `leader_score` | P0 | 1 | **待建** |
| G-05 | `run_leader_screen` Hub 入口 | P0 | 1 | **部分**（文档已写，代码待建） |
| G-06 | `RadarRow` 扩展字段 | P0 | 1 | **待建** |
| G-07 | 概念 + 行业统一 scoring | P1 | 4 | **规划** |
| G-08 | 情绪 gate 龙头选股 | P1 | 1 | **待建**（依赖 T-03） |

---

## 5. 策略与买卖点（S- / SP-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| S-01 | 短线策略族注册 | **待建** | 2 | [strategy-profiles.md](./strategy-profiles.md) |
| S-02 | 信号区 Profile 切换 | **待建** | 1 | 同上 |
| S-03 | 持仓退出规则集 | **部分** | 2 | [watchlist-positions.md](./watchlist-positions.md) |
| S-04 | 分 K 买卖参考线 | **待建** | 2 | — |
| S-05 | 开盘 30 分钟止损提醒 | **部分** | 2 | `position_anomaly` |
| SP-01 | Profile 枚举 + QSettings | **待建** | 1 | [strategy-profiles.md](./strategy-profiles.md) |
| SP-02 | 信号区 Profile 下拉 | **待建** | 1 | 同上 |
| SP-03 | 持仓区 header Profile | **待建** | 1 | 同上 |
| SP-04 | 新用户默认 Profile 配置 | **待建** | 1 | 同上 |
| SP-05 | LimitBoard / OvernightExit | **待建** | 2–5 | 同上 |
| — | 四套现有策略（双均线等） | **已有** | 0 | `strategies/registry.py` |

---

## 6. 仓位与自选（P-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| P-01 | 持仓记账 | **已有** | 0 | [watchlist-positions.md](./watchlist-positions.md) |
| P-02 | T+1 锁定 | **已有** | 0 | 同上 |
| P-03 | 浮盈 / exit_signal | **已有** | 0 | 同上 |
| P-04 | 计划仓位 % | **待建** | 3 | 同上 |
| P-05 | 情绪仓位系数对比 | **待建** | 3 | 依赖 T-03 |
| P-06 | 自选分组 Tab | **已有** | 0 | [watchlist-groups.md](./watchlist-groups.md) |
| P-07 | 分组级仓位汇总 | **待建** | 3 | 同上 |

---

## 7. 风控（K-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| K-01 | 总资金与风控参数 | **待建** | 3 | [risk-gate.md](./risk-gate.md) |
| K-02 | 单笔风险计算器 | **待建** | 3 | 同上 |
| K-03 | 当日已实现 + 浮亏汇总 | **待建** | 3 | 同上 |
| K-04 | normal / caution / halt | **待建** | 3 | 同上 |
| K-05 | 违规 off_plan 标记 | **待建** | 4 | [trading-plan-journal.md](./trading-plan-journal.md) |

---

## 8. 复盘与计划（J-）

| ID | 能力 | 状态 | Phase | 存储 | 文档 |
|----|------|------|-------|------|------|
| J-01 | `trading_plans` 表 | **待建** | 4 | App DB | [trading-plan-journal.md](./trading-plan-journal.md) |
| J-02 | `trade_journal` 表 | **待建** | 3–4 | App DB | 同上 |
| J-03 | `propose_trading_plan` AI | **待建** | 4 | — | [ai-data-routing.md](./ai-data-routing.md) |
| J-04 | 计划内 / 计划外校验 | **待建** | 4 | J-01, P-01 | 同上 |
| J-05 | 复盘报表（胜率 / 盈亏比） | **规划** | 5 | J-02 | 同上 |
| — | 笔记流水 `stock_note_entries` | **已有** | 0 | App DB | [stock-notes.md](./stock-notes.md) |

---

## 9. 通知（N-）

| ID | 能力 | 状态 | Phase | 文档 |
|----|------|------|-------|------|
| N-01 | 飞书 Webhook MVP | **已有** | 1 | [notifications.md](./notifications.md) |
| N-02 | 事件白名单 + 限频 | **已有** | 1 | 同上 |
| N-03 | 定时任务 screener 完成推送 | **已有** | 1 | 同上 |
| N-04 | 情绪 / 风控状态变更推送 | **待建** | 2 | 依赖 T-03, K-04 |
| N-05 | `notify_delivery_log` | **待建** | 2 | [data-design.md](./data-design.md) |
| N-06 | interactive 卡片 | **规划** | 3 | [notifications.md](./notifications.md) |

---

## 10. AI 工具（A-）

| ID | 工具 | 状态 | Phase | Skill（规划） |
|----|------|------|-------|---------------|
| A-01 | `get_emotion_cycle` | **待建** | 1 | vnpy-sentiment 扩展 |
| A-02 | `get_short_term_watchlist` | **待建** | 1 | vnpy-watchlist 扩展 |
| A-03 | `propose_trading_plan` | **待建** | 4 | vnpy-trading（新） |
| A-04 | `get_trade_journal` | **待建** | 4 | 同上 |
| A-05 | `check_risk_gate` | **待建** | 3 | 同上 |
| A-06 | `evaluate_entry_mode` | **待建** | 2 | vnpy-analysis 扩展 |
| A-07 | `run_leader_screen` | **待建** | 1 | vnpy-screening 扩展 |
| — | 现有 Skills 清单 | **已有** | 0 | [ai-data-routing.md](./ai-data-routing.md) |

---

## 11. 推荐实施顺序

与 [trading-system.md §12](./trading-system.md#12-实施分期) 对齐；可并行项用 `‖` 标注。

```text
Phase 1（当前）
├── N-01 ‖ N-02          飞书 MVP（独立、见效快）
├── T-03 → T-04 → T-05   情绪周期链
├── G-04 → G-02 → G-05   龙头评分 + Hub 入口
├── R-01 + 激进硬过滤
├── SP-01 → SP-02        Profile 基础
├── P-06（已有）          观察组 Tab
└── A-01, A-07           AI 择时 + 龙头

Phase 2
├── S-01, SP-05          短线策略插件
├── D-01, D-02           发现卡
├── R-02, R-03
└── N-03, N-04

Phase 3
├── K-01 ~ K-04, P-04, P-05
└── J-02（流水）

Phase 4
├── J-01, J-03, J-04, K-05
└── 复盘 UI

Phase 5
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
