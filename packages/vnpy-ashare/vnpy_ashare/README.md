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
├── config/           # runtime 常量、schema、bridge、vt_settings
├── domain/           # models、calendar、market_hours、signal_snapshot
├── data/             # bars、bar_store、bar_health、minute_periods
├── storage/          # app_db、universe、trade_calendar_store
├── backtest/         # CTA App/Engine、run_store、strategy_filter
├── quotes/           # 行情 Provider 与 TickFlow 客户端
├── screener/         # 选股（run / recipe / preset / pattern / data / dimensions / batch）
├── scheduler/        # 定时任务管理
├── jobs/             # 下载、补全、自动选股 Job
├── services/         # 业务 Service
├── ai/               # context/（组装与 store）、ui/（全屏页、悬浮球）
└── ui/
    ├── shell/        # main_window、nav；settings/、manager/
    ├── quotes/       # 看盘页（page / controllers / chart / table / panels / workers）
    ├── screener/     # 选股页（pages / widgets / dialogs / workers）
    ├── backtest/     # 回测页（pages / flow / chart / table）
    ├── scheduler/    # 定时任务页
    ├── components/   # 跨页复用
    └── styles/
```

## 核心入口

| 路径 | 说明 |
|------|------|
| `app/launcher.py` | GUI 启动（`run.py` 调用） |
| `services/` | Quote、Bar、Backtest、Screening 等 |
| `ai/context/store.py` | 终端 AI 共享内存态 |
| `data/bar_health.py` | 本地 K 线健康检测 |

元数据默认在 `~/.vntrader/zak.db`；CSV 备份见 `scripts/export_metadata.py`。

完整文档见 [docs/README.md](../../../docs/README.md)。
