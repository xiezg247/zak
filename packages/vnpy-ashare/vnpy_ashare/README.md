# vnpy_ashare

VeighNa **A 股现货** 图形终端：看盘（含板块资金、雷达）、条件选股、多因子配方、回测、AI 上下文与 Service 层。

## 在 VeighNa 中加载

```python
from vnpy_ashare.app.plugin import AshareApp

main_engine.add_app(AshareApp)
```

## 包结构

```
vnpy_ashare/
├── app/              # launcher、bootstrap、engine、events、engine_access
├── config/           # runtime 常量、schema、bridge、vt_settings、preferences/
├── domain/           # symbols、numbers、calendar、market_hours
├── integrations/     # 外部 API（Tushare、TickFlow 应用层、MCP；TickFlow SDK 见 vnpy_tickflow）
├── data/             # bars、bar_store、bar_health、minute_periods
├── storage/          # connection、repositories/、universe 编排
├── backtest/         # CTA App/Engine、run_store、strategy_filter
├── quotes/           # 行情 Provider 抽象、QuoteSnapshot、Redis 缓存
├── screener/         # 选股（run / recipe / preset / pattern / sector / data / dimensions / batch）
├── scheduler/        # 定时任务管理
├── jobs/             # 下载、补全、定时多因子选股 Job
├── services/         # 业务 Service
├── ai/               # context/（组装与 store）、ui/（全屏页、悬浮球）
└── ui/
    ├── shell/        # main_window、nav；settings/、manager/
    ├── features/     # 跨页 feature（stock_analysis 等）
    ├── quotes/       # 看盘页 + 雷达（page / radar / chart / table / panels / workers）
    ├── sector_flow/  # 板块资金页
    ├── screener/     # 选股 hub（条件选股 + 多因子配方；pages / widgets / dialogs / workers）
    ├── backtest/     # 回测页（pages / flow / chart / table）
    ├── scheduler/    # 定时任务页
    ├── components/   # 跨页复用
    └── styles/
```

## 核心入口

| 路径 | 说明 |
|------|------|
| `cli.py` | CLI 实现（仓库根 `cli.py` 或 `zak` 命令调用） |
| `app/launcher.py` | GUI 启动（仓库根 `run.py` 调用） |
| `services/` | Quote、Bar、Backtest、Screening 等 |
| `ai/context/store.py` | 终端 AI 共享内存态 |
| `data/bar_health.py` | 本地 K 线健康检测 |

元数据存 PostgreSQL（`DATABASE_URL`）；CSV 备份见 `cli.py meta export`。

完整文档见 [docs/README.md](../../../docs/README.md)。

## 分层约定

| 目录 | 职责 | 示例 |
|------|------|------|
| `domain/` | A 股领域模型与纯规则 | `StockItem`、`SignalSnapshot`、`symbols` 互转 |
| `services/signals/` | 策略信号盘中修饰与展示 | `runtime`（锚点、列表 cell、AI 摘要） |
| `integrations/` | 外部 API 薄封装 + 缓存 | Tushare 因子、TickFlow 行情、MCP |
| `screener/data/` | 选股数据源编排 | Redis + Tushare 合并 |
| `screener/sector/` | 行业分布汇总 | `sector_summary.py`（结果面板、板块维度、板块资金） |
| `quotes/` | 行情 Provider 抽象 | `QuoteProvider`、Redis 快照 |
| `services/` | 业务 Service | `QuoteService`、`ScreeningService`、`StockAnalysisService` |
| `services/stock/` | 个股分析子模块 | `profile`、`events`、`context` |
| `config/preferences/` | 用户偏好（QSettings） | `watchlist_signal`、`watchlist_position` |
| `ui/features/` | 跨页 UI 能力 | `stock_analysis`（看盘 / 选股 / 雷达入口） |
| `storage/repositories/` | PG `app` schema 表读写 | `watchlist`、`universe`、`financial`、`valuation`、`disclosure`、`trade_calendar`、`symbols` |
| `vnpy_common`（独立包） | 跨 App 基础设施 | paths、UI 主题 |

符号互转统一从 `domain.symbols` 导入；数值解析用 `domain.numbers.safe_float`。

## 数据源分工

| 场景 | 来源 | 典型入口 |
|------|------|----------|
| 实时 / 全市场快照 / Redis 行情 | **TickFlow** | `jobs/quotes.collect_market_quotes`、`screener/data/quotes_loader` |
| 历史日 K / 历史分 K 下载与补全 | **Tushare Pro** | `download_bars`、`download_period_bars` |
| 因子 / moneyflow / 财报等 | **Tushare Pro** | `integrations/tushare/*` |

配置：`TICKFLOW_API_KEY`（实时）、`TUSHARE_TOKEN`（历史与因子）。

Tushare 频率：日 K 接口默认限制 **450 次/分钟**（低于官方 500 上限，可设 `TUSHARE_DAILY_MAX_PER_MIN`）；分 K 见 `TUSHARE_STK_MINS_MAX_PER_MIN`。
