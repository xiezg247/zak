# 产品说明

个人 A 股现货量化终端：选股 → 看盘 → 回测 → AI 解读。交易风格以**极致短线为主、中线为辅**，见 [交易体系说明](./trading-system.md)；日路径见 [盘中工作流](./intraday-workflow.md)。

## 功能模块

| 模块 | 能力 |
|------|------|
| 看盘 | 自选 / 市场 / 板块资金 / 雷达 / 本地；五档、分 K、定时刷新 |
| 选股 | 条件选股、多因子配方、标杆对标、NL 解析；见 [选股 Hub](./screener-hub-guide.md)、[盘中选股](./intraday-screening.md) |
| 回测 | `AShareTemplate`（T+1、整手、只做多）；批量对比，见 [策略回测](./backtest-ux.md) |
| AI | Skills + MCP；悬浮球、Dock、全屏，见 [AI 数据路由](./ai-data-routing.md) |
| 运维 | 定时任务、K 线健康检测与补全、配置同步 |

## 左侧导航

```text
守则 | 自选 | 市场 | 板块资金 | 雷达 ‖ 选股 ‖ 信息流 ‖ AI 助手 ‖ 策略回测 | 回测对比
```

（`‖` 为侧栏分组；`守则` 默认首屏，见 [交易体系 §1.3](./trading-system.md#13-守则-playbook默认首屏)。）

| 快捷键 | 页 |
|--------|-----|
| `Ctrl+1` | 守则 |
| `Ctrl+2` | 自选 |
| `Ctrl+3` | 市场 |
| `Ctrl+4` | 板块资金 |
| `Ctrl+5` | 雷达 |
| `Ctrl+6` | 选股 Hub（条件选股 + 多因子配方） |
| `Ctrl+Shift+F` | 信息流 |
| `Ctrl+7` | AI 助手 |
| `Ctrl+8` | 策略回测 |
| `Ctrl+9` | 回测对比 |

菜单栏「后台」：`定时任务`（`Ctrl+0`）· `数据管理` · `本地数据`（`Ctrl+Shift+L`）

菜单栏「笔记」：`笔记中心`（`Ctrl+Shift+N`，见 [个股笔记](./stock-notes.md)）

| 页 | 说明 |
|----|------|
| 守则 | Playbook + 今日对照条 + 纪律 checklist |
| 自选 | 自选池、信号区、持仓记账；批量回测 |
| 市场 | 涨幅榜（Redis + TickFlow） |
| 板块资金 | 行业/概念资金；可跳转选股筛成分 |
| 雷达 | 十卡盘面扫描、选龙头；可跳转选股 |
| 选股 | Hub 双 Tab；操作见 [选股 Hub 指南](./screener-hub-guide.md) |
| 信息流 | B 站 UP 订阅，见 [info-feed.md](./info-feed.md) |
| AI 助手 | 全屏对话；看盘/选股页悬浮球 `Ctrl+L` / `⌘L` |
| 策略回测 / 回测对比 | 单票 / 批量回测与对比 |
| 定时任务 / 数据管理 / 本地数据 | 后台：采集、同步、K 线维护与补全 |

## 数据分工

| 数据 | 来源 | 用途 |
|------|------|------|
| 实时/历史行情、日分钟 K | TickFlow | 看盘、下载、回测 |
| 财务、资金流、估值 | Tushare | 选股因子 |
| 自选、全 A、回测/选股历史 | PostgreSQL `app` | 业务元数据 |
| K 线 | PostgreSQL `public` | 回测、本地页 |
| 涨幅榜快照 | Redis | 市场页 |

AI 与选股不编造行情；工具路由见 [ai-data-routing.md](./ai-data-routing.md)。

## AI 入口摘要

- **页面上下文**：Quote / Screening / Backtest 等 Service 写入 `context_store`
- **快速诊断**：`diagnose_stock`（问小达 MCP）
- **团队分析**：`/team 600519` 或「全面分析」，见 [智能体投研团队](./team-agent.md)
- **选股执行**：复杂条件经 `propose_screening` / `propose_recipe` 确认后执行

---

## 参考

[架构说明](./architecture.md) · [功能索引](./feature-index.md) · [数据流](./data-flow.md)
