# zak — A 股量化终端

基于 [VeighNa (vnpy)](https://www.vnpy.com) 的 **A 股现货** 图形化回测项目。行情主数据源为 **TickFlow Pro**，基本面/另类数据辅助为 **Tushare**。

## 功能特性

- A 股专项：默认回测参数、自选池、整手下单、T+1 规则
- 图形化 GUI：**A股日K 浏览**（全市场 5500+ 标的）、策略回测、数据管理
- TickFlow Pro：A 股日线 / 分钟线批量下载、实时行情推送
- Tushare：财务、资金流等（后续可扩展选股脚本）
- **AI 助手**：侧栏/全屏对话，Agent Skills 工具调用；终端上下文经 `context_store` + Service 共享
- **MCP 远端工具**：可通过 `mcp/mcp.json` 集成外部 MCP 服务器
- 本地 **SQLite** 存储（默认），可选 **QuestDB**（见下文）

## 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) 包管理器

## 快速开始

```bash
cd zak
bash scripts/install.sh

cp .env.example .env          # 填入 TICKFLOW_API_KEY
uv run python scripts/init_config.py

uv run python scripts/sync_universe.py  # 同步全 A 股标的列表（首次建议执行）
uv run python run.py                    # 启动 GUI（默认自选页，市场页可搜索加入自选）

# 自选池有标的后，批量下载日 K：
uv run python scripts/batch_download.py --start 2020-01-01 --end 2026-06-08
uv run python scripts/list_bars.py      # 确认本地数据
```

## A 股回测参数（自动配置）

启动时若检测到期货默认参数（`IF88.CFFEX` / `size=300`），会自动替换为 A 股配置：

| 界面字段 | A 股取值 | 说明 |
|---------|---------|------|
| 本地代码 | `600519.SSE` | 6 位代码 + `.SSE` / `.SZSE` / `.BSE` |
| 合约乘数 | **1** | 每股乘数（界面仍显示期货术语） |
| 价格跳动 | **0.01** | 最小报价单位 |
| 手续费率 | **0.00045** | 佣金万二 + 印花税万五折中 |
| 交易滑点 | **0.01** | 1 个最小价位 |
| 回测资金 | 100000 | 10 万 |

> 策略回测页已中文化关键字段（股票代码、每股乘数）；其余控件沿用 vnpy 回测引擎，填对参数即可。

## 策略开发

继承 `AShareTemplate` 而非直接继承 `CtaTemplate`：

```python
from ashare_template import AShareTemplate

class MyStrategy(AShareTemplate):
    def on_bar(self, bar):
        self.buy_stock(bar.close_price, 100)                    # 整手买入
        self.sell_stock(bar.close_price, 100, bar.datetime.date())  # T+1 卖出
```

内置示例：`AshareDoubleMaStrategy`（双均线，仅做多）

## 自选池与标的列表

自选池、全 A 股列表存放在 `~/.vntrader/zak.db`（与 K 线库 `~/.vntrader/database.db` 同目录）。

```bash
# 同步全 A 股列表
uv run python scripts/sync_universe.py

# 批量下载自选池 K 线
uv run python scripts/batch_download.py --start 2020-01-01 --end 2026-06-08

# 查看入库状态
uv run python scripts/list_bars.py

# 单元测试
uv run python -m unittest discover -s tests -v

# 备份 / 恢复（CSV 仅作导入导出，非主存储）
uv run python scripts/export_metadata.py
uv run python scripts/import_metadata.py --watchlist data/backup/watchlist.csv
```

## 数据库（可选 QuestDB）

默认使用 **SQLite**（`vnpy_sqlite`），无需额外服务。

后续若数据量增大或需要盘中高频写入，可切换 [vnpy_questdb](https://github.com/vnpy/vnpy_questdb)：

```bash
uv sync --extra questdb
bash scripts/start_questdb.sh
# .env: DATABASE_NAME=questdb，并取消注释 QUESTDB_* 配置
uv run python scripts/init_config.py
uv run python scripts/check_database.py
```

切回 SQLite：`.env` 设 `DATABASE_NAME=sqlite`，重新执行 `init_config.py`。

## 文档

- [产品方案](docs/product-plan.md) — A 股回测 + 看盘 + AI + 选股 + 策略实盘路径
- [架构说明](docs/architecture.md) — 与 vnpy 默认 Trader 的关系、当前 UI 分层
- [数据设计](docs/data-design.md) — 三个 SQLite 数据库 + Redis 缓存层
- [策略回测交互规格](docs/backtest-ux.md) — 看盘→回测联动、批量回测分阶段设计
- [AI 数据路由说明](docs/ai-data-routing.md) — AI 助手各类问题对应的数据源与工具
- [后续规划](docs/roadmap.md) — A 股 Gateway 实盘、PaperAccount、看盘行情切换等

## 项目结构

```
zak/
├── run.py                         # GUI 入口（调用 vnpy_ashare.launcher）
├── strategies/                    # CTA 策略（AShareTemplate + 双均线等）
│   ├── ashare_template.py         # A 股策略基类
│   ├── double_ma_strategy.py      # 双均线示例策略
│   ├── signals.py                 # 策略信号定义
│   └── registry.py                # 策略元数据注册表
├── docs/                          # 架构说明与后续规划
├── vnpy_ashare/                   # VeighNa A 股行情 App
│   ├── launcher.py                # GUI 启动逻辑
│   ├── engine.py                  # A 股引擎（含 Service 层初始化）
│   ├── paths.py / config.py       # 路径与 A 股常量
│   ├── models.py / bars.py        # 标的模型与 K 线下载
│   ├── app_db.py / universe.py    # 元数据库与全市场同步
│   ├── bar_health.py / bar_store.py # K 线健康状态与读取
│   ├── calendar.py                # 交易日历
│   ├── backtester_app.py          # 回测 App 封装
│   ├── backtester_engine.py       # 回测引擎扩展
│   ├── ai/                        # context_store、页面上下文、全屏页
│   ├── quotes/                    # 行情 Provider 抽象（TickFlow/Redis/Gateway）
│   ├── services/                  # Service 业务层（6 个 Service）
│   ├── screener/                  # 选股模块（13 文件：因子/规则/方案/执行）
│   ├── backtest/                  # 回测结果落地
│   ├── scheduler/                 # 定时任务调度
│   ├── jobs/                      # 任务定义（下载/行情/同步）
│   └── ui/                        # 主窗口、导航、行情页、回测页、选股页
├── vnpy_llm/                      # 大模型对话插件（client / engine / panel）
├── vnpy_skills/                   # Agent Skill 引擎（工具注册/执行/注入）
├── vnpy_mcp/                      # MCP 远端工具集成
├── vnpy_tickflow/                 # TickFlow 行情适配器
├── skills/                        # 业务 Skill 实现
│   ├── vnpy_context_skill.py      # 终端上下文
│   ├── vnpy_data_skill.py         # 数据查询
│   ├── vnpy_backtest_skill.py     # 回测
│   ├── vnpy_screening_skill.py    # 选股
│   ├── vnpy_watchlist_skill.py    # 自选管理
│   ├── vnpy_analysis_skill.py     # 技术分析 + 综合诊断
│   ├── registry.py                # Skill 元数据注册
│   ├── tickflow/                  # TickFlow Agent Skill
│   └── tushare-data/              # Tushare Agent Skill
├── mcp/                           # MCP 外接配置文件
├── docker-compose.yml             # QuestDB（可选）
└── scripts/
    ├── init_config.py
    ├── start_questdb.sh
    ├── check_database.py
    ├── batch_download.py
    ├── download_data.py
    ├── list_bars.py
    ├── sync_universe.py           # 同步全 A 股标的列表
    ├── sync_skills.py             # 同步 Agent Skills
    ├── quote_collector.py         # 行情收集器（Redis）
    ├── list_mcp_tools.py          # 列出通达信 MCP 工具
    ├── run_screener.py            # 命令行选股筛选
    ├── export_metadata.py         # 导出元数据
    └── import_metadata.py         # 导入元数据
```

## 数据源分工

| 用途 | 数据源 |
|------|--------|
| A 股 K 线（日/分钟） | TickFlow Pro（`DATAFEED_NAME=tickflow`） |
| 财务 / 资金流 / 选股 | Tushare（独立脚本，非 GUI 行情） |

## 常见问题

**Q: 策略列表里有多个双均线？**

选 `AshareDoubleMaStrategy`（本项目 A 股版本），不要选 vnpy 内置的 `DoubleMaStrategy`（含做空逻辑）。

**Q: 回测界面仍是期货样式？**

vnpy CTA 模块 UI 不可改，参数正确即可。启动 `run.py` 会自动写入 A 股默认值。

**Q: 分钟线下载失败？**

缩短日期范围（建议 ≤ 6 个月），并确认已配置 TickFlow Pro API Key。
