# 配置分级热加载

系统配置页（`ui/shell/settings/`）保存后按项**分级反馈**并尽力热应用；无法安全热加载的标注需重启。

| 层 | 文件 | 用途 |
|----|------|------|
| `.env` | 密钥与基础设施 | TickFlow、Tushare、Redis、LLM、PG、飞书、硬过滤覆盖 |
| `vt_setting.json` | VeighNa SETTINGS 镜像 | 日志、字体、datafeed、K 线库 |

另有 **QSettings**（业务页即时写入，无需重启）。

## 三档

| 档位 | 含义 | 典型项 |
|------|------|--------|
| **即时** | 保存后立刻生效 | 日志、字体、LLM、飞书通知、`RECIPE_*`、QSettings 业务键 |
| **软重载** | 重建 datafeed / 下次调度读新 env | `DATAFEED_*`、`TICKFLOW_*`、`TUSHARE_*`、`REDIS_URL`、采集间隔 |
| **需重启** | 仅落盘，提示重启 | K 线库 `database.*`、元数据路径 |

`.env` 保存可调「从 .env 同步」写入 `vt_setting.json`。保存成功按项列出 ✓/⚠ 文案；顶栏保留「重载 LLM」兜底。

## QSettings 与专题文档

| 键前缀 | 文档 |
|--------|------|
| `trading/strategy_profile` | [策略 Profile](./strategy-profiles.md) |
| `trading/total_capital` 等 | [风控](./risk-gate.md) |
| `notify/events` | [通知](./notifications.md) |
| `screener_ui/hard_filter_*` | [盘中选股](./intraday-screening.md) |
| `trading/emotion/*` | [情绪周期](./emotion-cycle.md) |
| `watchlist_groups/*` | [自选页](./watchlist.md) |

## 实现入口

`config/apply.py`（`ApplyTier`、`apply_runtime_settings`）← `ui/shell/settings/dialog.py`。  
相关：`env_store.py`、`datafeed_reload.py`；测试 `tests/ashare/test_config_apply.py`。

---

[架构说明 §配置](./architecture.md#5-配置)
