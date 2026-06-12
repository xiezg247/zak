# vnpy_ashare

VeighNa **A 股现货** 图形终端：看盘、策略选股、自动选股、回测、AI 上下文与 Service 层。

## 在 VeighNa 中加载

```python
from vnpy_ashare import AshareApp

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
├── screener/         # 选股（run / recipe / preset / pattern / data / dimensions / batch）
├── scheduler/        # 定时任务管理
├── jobs/             # 下载、补全、自动选股 Job
├── services/         # 业务 Service
├── ai/               # context/（组装与 store）、ui/（全屏页、悬浮球）
└── ui/
    ├── shell/        # main_window、nav；settings/、manager/
    ├── features/     # 跨页 feature（stock_analysis 等）
    ├── quotes/       # 看盘页（page / controllers / features / chart / table / panels / workers）
    ├── screener/     # 选股页（pages / widgets / dialogs / workers）
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

元数据默认在 `~/.vntrader/zak.db`；CSV 备份见 `cli.py meta export`。

完整文档见 [docs/README.md](../../../docs/README.md)。

## 分层约定

| 目录 | 职责 | 示例 |
|------|------|------|
| `domain/` | A 股领域模型与纯规则 | `StockItem`、`SignalSnapshot`、`symbols` 互转 |
| `services/signals/` | 策略信号盘中修饰与展示 | `runtime`（锚点、列表 cell、AI 摘要） |
| `integrations/` | 外部 API 薄封装 + 缓存 | Tushare 因子、TickFlow 行情、MCP |
| `screener/data/` | 选股数据源编排 | Redis + Tushare 合并 |
| `quotes/` | 行情 Provider 抽象 | `QuoteProvider`、Redis 快照 |
| `services/` | 业务 Service | `QuoteService`、`ScreeningService`、`StockAnalysisService` |
| `services/stock/` | 个股分析子模块 | `profile`、`events`、`context` |
| `config/preferences/` | 用户偏好（QSettings） | `watchlist_signal`、`watchlist_position` |
| `ui/features/` | 跨页 UI 能力 | `stock_analysis`（看盘 / 选股 / 雷达入口） |
| `storage/repositories/` | zak.db 表读写 | `watchlist`、`universe`、`financial`、`valuation`、`disclosure`、`trade_calendar`、`symbols` |
| `vnpy_common`（独立包） | 跨 App 基础设施 | paths、UI 主题 |

符号互转统一从 `domain.symbols` 导入；数值解析用 `domain.numbers.safe_float`。
