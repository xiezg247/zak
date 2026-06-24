# 产品说明

个人 A 股现货量化终端：选股 → 看盘 → 回测 → AI 解读。交易风格以**极致短线为主、中线为辅**，见 [交易体系说明](./trading-system.md)；日路径见 [盘中工作流](./intraday-workflow.md)。

## 功能模块

| 模块 | 能力 |
|------|------|
| 看盘 | 自选 / 市场 / 板块资金 / 雷达 / 本地；五档、分 K、定时刷新 |
| 选股 | 条件选股、多因子配方、标杆对标、NL 解析、结果行业分布 |
| 回测 | `AShareTemplate`（T+1、整手、只做多）；批量对比 |
| AI | Skills + MCP；悬浮球、Dock、全屏 |
| 运维 | 定时任务、K 线健康检测与补全、配置同步 |

## 左侧导航

```text
守则 | 自选 | 市场 | 板块资金 | 雷达 ‖ 选股 ‖ 信息流 ‖ AI 助手 ‖ 策略回测 | 回测对比
```

（`‖` 表示侧栏分组分隔线；`守则` 为默认首屏，详见 [交易体系 §1.3](./trading-system.md#13-守则-playbook默认首屏)。）

| 快捷键 | 页 |
|--------|-----|
| `Ctrl+1` | 守则（交易体系 Playbook） |
| `Ctrl+2` | 自选 |
| `Ctrl+3` | 市场 |
| `Ctrl+4` | 板块资金 |
| `Ctrl+5` | 雷达 |
| `Ctrl+6` | 选股 |
| `Ctrl+Shift+F` | 信息流 |
| `Ctrl+7` | AI 助手 |
| `Ctrl+8` | 策略回测 |
| `Ctrl+9` | 回测对比 |

菜单栏「后台」：`定时任务`（`Ctrl+0`）· `数据管理` · `本地数据`（`Ctrl+Shift+L`）

菜单栏「笔记」：`笔记中心`（`Ctrl+Shift+N`；备忘 / 流水 / 分析报告，见 [stock-notes.md](./stock-notes.md)）

| 页 | 说明 |
|----|------|
| 守则 | 默认首屏；规则 Markdown + 今日对照条 + 纪律 checklist；`Ctrl+1` |
| 自选 | 自选池跟踪；批量回测、标杆对标 |
| 市场 | 涨幅榜（Redis + TickFlow） |
| 板块资金 | 行业/概念资金流向监控；可跳转条件选股做行业成分筛选 |
| 雷达 | 多卡片盘面扫描（主线、共振、**选龙头**等）；权重变更后相关卡片全量重算；可跳转选股 |
| 选股 | Hub 页，内嵌「条件选股」「多因子配方」两个 Tab；操作速查见 [选股 Hub 使用指南](./screener-hub-guide.md) |
| 信息流 | B 站 UP 订阅时间线；定时/手动同步；见 [info-feed.md](./info-feed.md) |
| AI 助手 | 全屏对话；看盘/选股页另有悬浮球（`Ctrl+L` / `⌘L`） |
| 策略回测 | 单标的回测 |
| 回测对比 | 批量回测批次对比 |
| 定时任务 | 下载、行情采集、universe 同步、盘中多因子、B 站订阅同步 |
| 数据管理 | vnpy K 线维护 |
| 本地数据 | 本地 K 线起止、健康状态、补全（后台弹窗，非侧栏页） |

### 选股 Hub

| Tab | 说明 |
|-----|------|
| 条件选股 | 规则 / preset 筛选、方案保存、形态/雷达/行业快捷入口、批量入自选 |
| 多因子配方 | Recipe 多因子打分、运行历史收件箱；左侧 `[盘中]` / `[盘后]` 过滤 |

两 Tab 共用：

- 左栏 Accordion 配置 + 硬过滤（保守/均衡/激进模板、行业/板块白名单）
- 结果洞察区：`ScreenerResultInsights`（diff + 行业分布）
- 结果操作：全选、入自选、下载日 K、单票/批量回测、找同类、**导出 CSV**

UI 细节见 [盘中选股 §5](./intraday-screening.md#5-ui)。

## 数据分工

| 数据 | 来源 | 用途 |
|------|------|------|
| 实时/历史行情、日分钟 K | TickFlow | 看盘、下载、回测 |
| 财务、资金流、估值 | Tushare | 选股因子 |
| 自选、全 A 列表、回测/选股历史 | `~/.vntrader/zak.db` | 元数据（固定 SQLite） |
| 本地 K 线 | `~/.vntrader/database.db` 或 PostgreSQL | 回测、本地页（唯一可切换存储） |
| 涨幅榜快照 | Redis | 市场页 |

AI 与选股不编造行情；数值来自上述数据源。工具路由见 [ai-data-routing.md](./ai-data-routing.md)。

## 选股

**条件选股**（`screener/run/`）：因子 → 规则引擎 → 方案持久化 → GUI → 入自选 / 回测。

**多因子配方**（`auto_screener_page.py`）：Recipe 并行维度打分（`recipe_*`）+ 运行历史；定时任务或 AI 写入收件箱。硬过滤支持 ST、停牌、新股、涨跌停、流动性、行业/板块白名单等（`hard_filters.py` + `ScreenerHardFilterPanel`；QSettings + `RECIPE_*` 环境变量）。

**行业分布**（`screener/sector/sector_summary.py`）：选股结果按 Tushare 行业映射聚合，供结果面板、`sector_strength` 维度与板块资金页共用。

**AI 对话选股**：

| 路径 | 工具 | 条件 |
|------|------|------|
| 自动 preset | `screen_by_condition` | 内置 preset |
| 自动形态 | `screen_by_pattern` | 老鸭头/均线多头/W底/主题投资 |
| 盘中多因子 | `run_recipe` | 内置/用户配方 |
| 确认 | `propose_screening` / `propose_recipe` | 已保存方案、复杂条件 |

**标杆对标**（`reference_peer.py`）：以标杆股为锚，按行业、估值、走势找同类标的。

## 回测

见 [backtest-ux.md](./backtest-ux.md)。

- `AShareTemplate`：仅做多、100 股整手、T+1
- 看盘选中标的 → 策略回测页预填 `vt_symbol`
- 自选 / 选股批量回测 → 回测对比页
- 摘要写入 `backtest_runs`，AI 通过 Skill 读取

## AI

7 个 Service 写入 `context_store`；Skills 只读调用：

| Skill | 能力 |
|-------|------|
| vnpy-context | 当前页面与选中标的 |
| vnpy-data | K 线查询 |
| vnpy-screening | 选股、多因子配方（run_recipe） |
| vnpy-backtest | 回测结果 |
| vnpy-watchlist | 自选 CRUD |
| vnpy-analysis | 技术面、选股解读、走势情景 |
| tdx-stock-diagnose | 单票快速综合诊断（问小达 MCP） |
| tdx-financial-analysis | 财务深度分析（团队模式 financial Agent） |
| tdx-risk-analysis | 风险画像（团队模式 risk Agent） |
| vnpy-sentiment | A 股恐贪指数 |

**团队全面分析**（`team_analysis` 意图）：financial / risk / strategy 三 Agent 并行 + chief 汇总。触发：「全面分析」「团队分析」或 `/team 600519`。与 `diagnose_stock` 互补——前者深挖分维度，后者快速概览。详见 [智能体投研团队](./team-agent.md)。

LLM 不编造价格；复杂选股条件须用户确认后执行。

---

## 参考

- [架构说明](./architecture.md)
- [信息流](./info-feed.md)
- [选股 Hub 使用指南](./screener-hub-guide.md)
- [盘中选股](./intraday-screening.md)
- [AI 数据路由](./ai-data-routing.md)
- [智能体投研团队](./team-agent.md)
- [策略回测](./backtest-ux.md)
