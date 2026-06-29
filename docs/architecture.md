# 架构说明

> 产品导航见 [产品说明](./product-plan.md)；数据见 [数据设计](./data-design.md)。

---

## 1. 主窗口

继承 `vnpy.trader.ui.MainWindow`：左侧导航 + `StackedWidget` 内容区，可选 AI Dock。  
导航：`ui/shell/nav.py`（`APP_NAV_GROUPS` 侧栏 + 菜单栏「回测」「后台」弹窗）。

领域模型：`StockItem`、`QuoteSnapshot`（非 vnpy `TickData`）。

---

## 2. 包结构（摘要）

| 包 | 职责 |
|----|------|
| `vnpy-ashare` | 看盘、选股、回测、调度、通知、守则、信息流 |
| `vnpy-tickflow` | TickFlow 行情与 K 线 |
| `vnpy-llm` | 对话、路由、AgentGateway |
| `vnpy-skills` / `vnpy-mcp` | Skill 与远端工具 |
| `vnpy-common` | 路径、AI 协议、LLM 桥接端口 |

`vnpy_ashare` 内：`quotes/`（行情）、`screener/`（选股）、`services/`、`ui/`（页面）、`notifications/`、`trading/`。

---

## 3. 行情（`quotes/`）

```text
core/     QuoteSnapshot、Redis/TickFlow Provider
rank/     排行
market/   广度、环境、emotion_cycle
radar/    雷达卡、共振、龙头
misc/     持仓异动
```

看盘 UI 只依赖 `QuoteSnapshot`：`TickflowQuoteProvider`（自选）、`RedisQuoteProvider`（市场）。

---

## 4. 主要页面

| 页 | 路径 |
|----|------|
| 守则 | `ui/home/` |
| 自选/市场/雷达 | `ui/quotes/` |
| 板块资金 | `ui/sector_flow/` |
| 选股 Hub | `ui/screener/pages/screener_hub_page.py` |
| 回测 | `ui/backtest/`（菜单栏弹窗，见 `ui/backtest/dialog.py`） |
| 信息流 | `ui/features/info_feed/` |

自选页组合：主表 + 信号区 + 持仓区（见 [自选页说明](./watchlist.md)）。

---

## 5. 配置

`.env` 为密钥真源 → `config_bridge` → `vt_setting.json`；GUI 在 `ui/shell/settings/`。  
分级热加载见 [config-hot-reload](./config-hot-reload.md)。

---

## 6. AI

| 入口 | 说明 |
|------|------|
| 悬浮球 | 看盘/选股页 `Ctrl+L` |
| Dock / 全屏 | 导航「AI 助手」 |

`context_store`：Quote、Screening、Backtest 等 Service 写入；Skills 只读调用。

**桥接**：`vnpy_llm` 不直接 import `vnpy_ashare`，经 `vnpy_common` 端口在启动时注册（`install_shared_bridges()`）。

**编排**：`AgentGateway` → 意图路由 → ReAct 工具循环或 `team_analysis` / `market` 专用编排。  
路由与工具表见 [AI 数据路由](./ai-data-routing.md)；团队分析见 [team-agent](./team-agent.md)。

---

## 7. 本地 K 线

`bar_health.py`：OK / STALE / GAPS / UNKNOWN。交易日历来自 Tushare → `trade_calendar`。

---

## 参考

[编码规范](./coding-standards.md) · [数据流](./data-flow.md)
