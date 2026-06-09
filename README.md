# zak — A 股量化终端

基于 [VeighNa (vnpy)](https://www.vnpy.com) 的 **A 股现货** 图形化终端：看盘、选股、回测、AI 助手一体化。

| 用途 | 数据源 |
|------|--------|
| 行情 / 日分钟 K | TickFlow Pro |
| 财务 / 资金流 / 选股因子 | Tushare |

## 功能

- **看盘**：自选 / 市场 / 本地；TickFlow 行情与五档、Redis 涨幅榜、分 K 图表
- **选股**：策略选股（规则 + 方案）与自动选股（配方 + 定时收件箱）；NL 解析、标杆对标、批量入自选
- **回测**：`AShareTemplate`（T+1、整手、只做多）；看盘联动、批量回测与回测对比
- **AI**：悬浮球 + Dock + 全屏；Agent Skills + MCP；多会话、流式停止、配置热重载
- **运维**：定时任务、本地 K 线健康检测与补全、`.env` ↔ `vt_setting.json` 单源同步

## 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

## 快速开始

```bash
cd zak
bash scripts/install.sh

cp .env.example .env          # 填入 TICKFLOW_API_KEY、TUSHARE_TOKEN 等
uv run python scripts/init_config.py

uv run python scripts/sync_universe.py   # 首次建议：同步全 A 股列表
uv run python run.py                     # 启动 GUI

# 自选池有标的后，批量下载日 K：
uv run python scripts/batch_download.py --start 2020-01-01 --end 2026-06-08
uv run python scripts/list_bars.py
```

## 回测默认参数

启动时若检测到期货默认参数，会自动写入 A 股配置：

| 字段 | 取值 | 说明 |
|------|------|------|
| 股票代码 | `600519.SSE` | 6 位代码 + `.SSE` / `.SZSE` / `.BSE` |
| 每股乘数 | 1 | 每股价钱乘数，整手归一由策略模板处理 |
| 价格跳动 | 0.01 | 最小报价单位 |
| 手续费率 | 0.00045 | 佣金 + 印花税折中 |
| 滑点 | 0.01 | 1 个最小价位 |
| 回测资金 | 100000 | 10 万 |

## 策略开发

继承 `AShareTemplate` 而非 `CtaTemplate`：

```python
from ashare_template import AShareTemplate

class MyStrategy(AShareTemplate):
    def on_bar(self, bar):
        self.buy_stock(bar.close_price, 100)
        self.sell_stock(bar.close_price, 100, bar.datetime.date())  # T+1
```

内置示例：`AshareDoubleMaStrategy`（双均线，仅做多）

## 数据存储

项目采用**双存储结构**，元数据与行情数据分离：

| 存储位置 | 数据类型 | 可否切换 |
|----------|----------|----------|
| `~/.vntrader/zak.db` | 自选池、全 A 股列表、交易日历、回测/选股历史 | **固定 SQLite** |
| `~/.vntrader/llm_chat.db` | AI 对话会话与消息 | **固定 SQLite** |
| `~/.vntrader/database.db` | K 线数据（日线/分钟线/Tick） | SQLite 或 PostgreSQL |

K 线数据通过 `DATABASE_NAME` 切换存储后端，默认 `sqlite` 即可使用；如需远程共享或多进程查询，可切换为 `postgresql`。

### 切换为 PostgreSQL

```bash
# 1. 修改 .env
DATABASE_NAME=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=zak
POSTGRES_PASSWORD=zak
POSTGRES_DATABASE=zak

# 2. 安装依赖
uv sync --extra postgresql

# 3. 启动 PostgreSQL（本地 Docker）
bash scripts/start_postgresql.sh

# 4. 同步配置
uv run python scripts/init_config.py
```

> **注意**：仅 K 线数据切换存储，元数据（`zak.db`）和 AI 对话（`llm_chat.db`）始终为本机 SQLite，不受 `DATABASE_NAME` 影响。

## 脚本

```bash
uv run python scripts/sync_universe.py
uv run python scripts/batch_download.py --start 2020-01-01 --end 2026-06-08
uv run python scripts/list_bars.py
uv run python scripts/export_metadata.py
uv run python -m unittest discover -s tests -v
```

## 文档

| 文档 | 说明 |
|------|------|
| [文档索引](docs/README.md) | 全部文档入口 |
| [产品说明](docs/product-plan.md) | 功能与导航 |
| [架构说明](docs/architecture.md) | GUI 分层、Service、行情 Provider |
| [数据设计](docs/data-design.md) | SQLite ×3 + Redis |
| [策略回测](docs/backtest-ux.md) | 联动、批量回测、AI 上下文 |
| [AI 数据路由](docs/ai-data-routing.md) | Skill / MCP 与数据源 |

## 项目结构

```
zak/
├── run.py                    # GUI 入口
├── strategies/               # AShareTemplate 策略
├── vnpy_ashare/              # 主 App：看盘、选股、回测、调度、AI 上下文
├── vnpy_llm/                 # LLM 对话插件
├── vnpy_skills/              # Agent Skill 引擎
├── vnpy_mcp/                 # MCP 远端工具
├── vnpy_tickflow/            # TickFlow 适配器
├── skills/                   # 业务 Skill（context / data / screening / backtest 等）
├── mcp/                      # MCP 配置
├── docs/                     # 产品与架构文档
└── scripts/                  # 安装、下载、同步、选股 CLI
```

## 常见问题

**策略列表里有多个双均线？** 选 `AshareDoubleMaStrategy`（本项目 A 股版），不要选 vnpy 内置 `DoubleMaStrategy`。

**回测界面仍是期货样式？** vnpy CTA UI 不可改，参数正确即可；`run.py` 会自动写入 A 股默认值。

**分钟线下载失败？** 缩短日期范围（建议 ≤ 6 个月），并确认 TickFlow API Key 有效。
