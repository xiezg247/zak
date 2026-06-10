# 产品说明

个人 A 股现货量化终端：选股 → 看盘 → 回测 → AI 解读。技术细节见 [architecture.md](./architecture.md)。

## 功能模块

| 模块 | 能力 |
|------|------|
| 看盘 | 自选 / 市场 / 本地；五档、分 K、定时刷新 |
| 选股 | 策略选股、自动选股、标杆对标、NL 解析 |
| 回测 | `AShareTemplate`（T+1、整手、只做多）；批量对比 |
| AI | Skills + MCP；悬浮球、Dock、全屏 |
| 运维 | 定时任务、K 线健康检测与补全、配置同步 |

## 左侧导航

```text
自选 | 市场 | 策略选股 | 自动选股 | 本地 | AI 助手 | 策略回测 | 回测对比 | 定时任务 | 数据管理
```

| 页 | 说明 |
|----|------|
| 自选 | 自选池跟踪；批量回测、标杆对标 |
| 市场 | 涨幅榜（Redis + TickFlow） |
| 策略选股 | 规则筛选、方案保存、批量入自选 |
| 自动选股 | 多因子配方、定时/AI 结果收件箱 |
| 本地 | 本地 K 线起止、健康状态、补全 |
| AI 助手 | 全屏对话；看盘页另有悬浮球（`Ctrl+L` / `⌘L`） |
| 策略回测 | 单标的回测 |
| 回测对比 | 批量回测批次对比 |
| 定时任务 | 下载、行情采集、universe 同步、自动选股 |
| 数据管理 | vnpy K 线维护 |

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

**策略选股**（`screener/`）：因子 → 规则引擎 → 方案持久化 → GUI → 入自选 / 回测。

**自动选股**（`auto_screener_page.py`）：多因子配方（`recipe_*`）+ 运行历史；定时任务或 AI 写入收件箱。

**AI 对话选股**：

| 路径 | 工具 | 条件 |
|------|------|------|
| 自动 preset | `screen_by_condition` | 内置 preset |
| 自动形态 | `screen_by_pattern` | 老鸭头/均线多头/W底/主题投资 |
| 确认 | `propose_screening` | 已保存方案、复杂条件 |

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
| vnpy-analysis | 技术面、综合诊断 |
| vnpy-sentiment | A 股恐贪指数 |

LLM 不编造价格；复杂选股条件须用户确认后执行。
