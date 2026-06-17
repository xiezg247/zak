# 配置分级热加载

## 概述

系统配置页（`ui/shell/settings/`）保存后按配置项**分级反馈**并**尽力热应用**；无法安全热加载的项标注需重启。

| 层 | 文件 | 用途 |
|----|------|------|
| 环境变量 | `.env` | 密钥与基础设施（TickFlow、Tushare、Redis、LLM、PG 连接等） |
| 运行时 | `vt_setting.json` | VeighNa `SETTINGS` 镜像（字体、日志、datafeed、K 线库等） |

## 生效矩阵

### vt_setting.json（配置页可编辑）

| 配置项 | 档位 | 保存后行为 |
|--------|------|------------|
| `log.active` | **即时** | 合并 SETTINGS + 调整 root logger |
| `log.level` | **即时** | 同上 |
| `datafeed.name` / `username` / `password` | **软重载** | 重建 vnpy datafeed 单例 + 重置行情 Provider |
| `font.family` / `font.size` | **即时** | QApplication 字体 + theme_manager 重刷 QSS |
| `database.*`（K 线库） | **需重启** | 连接池与 bar_store 绑定启动路径 |
| `database.meta.*` | **需重启** | 元数据路径；配置页只读展示 |

### .env（配置页可编辑）

保存时写入 `.env` 并调用 `apply_env_side_effects`。若需同步到 `vt_setting.json`，使用「从 .env 同步」。

| 配置项 | 档位 | 行为 |
|--------|------|------|
| `LLM_API_*` | **即时** | `load_dotenv` + `LlmEngine.reload_config()` |
| `LLM_TEAM_DEEP_MODE` | **即时** | QSettings `llm/team_deep_mode` 或 env；控制团队分析 prefetch 深度 |
| `DATAFEED_NAME` / `TICKFLOW_*` / `TUSHARE_*` | **软重载** | 同步写入 vt_setting 后合并 SETTINGS |
| `DATABASE_NAME` / `POSTGRES_*` | **需重启** | 同步后标注重启 |
| `REDIS_URL` / `QUOTE_COLLECT_INTERVAL` | **软重载** | 进程内 `load_dotenv`；采集任务下次调度读新 env |
| `FEISHU_WEBHOOK_URL` / `FEISHU_WEBHOOK_SECRET` | **即时** | `NotificationService.reload()` |
| `NOTIFY_ENABLED` | **即时** | 总开关 |
| `NOTIFY_MIN_INTERVAL_SEC` | **即时** | 出站限频 |
| `RECIPE_*`（硬过滤覆盖） | **即时** | 选股下次运行读新 env；见 [intraday-screening §2.3](./intraday-screening.md#23-硬过滤) |

### QSettings（配置页 / 业务页，即时）

| 键前缀 | 说明 | 文档 |
|--------|------|------|
| `trading/strategy_profile` | 策略 Profile | [strategy-profiles.md](./strategy-profiles.md) |
| `trading/total_capital` 等 | 风控参数 | [risk-gate.md](./risk-gate.md) |
| `notify/events` | 飞书事件订阅多选 | [notifications.md](./notifications.md) |
| `screener_ui/hard_filter_*` | 硬过滤模板与阈值 | [intraday-screening.md](./intraday-screening.md) |
| `watchlist_groups/*` | 分组 Tab 状态 | [watchlist-groups.md](./watchlist-groups.md) |

> 交易 / 风控 / 通知模块实现前，配置页可先占位；保存行为与上表档位一致。

## 架构

```
SettingsDialog._save / _sync_from_env
        │
        ▼
save_runtime_settings / sync_vt_settings_from_env
        │
        ▼
config.apply.apply_runtime_settings(changed, context)
        │
        ├── reload_vnpy_settings()
        ├── instant  → _apply_log_settings() / _apply_font_settings()
        ├── soft     → reload_datafeed_stack()
        ├── restart  → 仅结果文案
        └── context.llm_engine → reload_config()
```

### 核心类型

```python
ApplyTier = "instant" | "soft_reload" | "restart_required"

@dataclass
class ApplyResult:
    key: str
    label: str
    tier: ApplyTier
    success: bool
    message: str
```

`ApplyContext` 注入可选依赖：`llm_engine`（AI 重载）、`scheduler`（预留）。

### UX 规范

保存/同步成功后按项列出：

```
配置已写入 ~/.vntrader/vt_setting.json
✓ 日志级别 — 已立即生效
✓ 数据源 — 已更新全局 SETTINGS
⚠ 字体 — 已保存，需重启应用后生效
```

- 全部即时/软重载 → `success`
- 含需重启项 → 仍 `success`，文案含 ⚠
- 应用失败 → 对应行 warning，不阻断保存

顶栏保留「重载 LLM」作手动兜底。

## 相关文件

- `packages/vnpy-ashare/vnpy_ashare/config/env_store.py`
- `packages/vnpy-ashare/vnpy_ashare/config/datafeed_reload.py`
- `packages/vnpy-ashare/vnpy_ashare/config/apply.py`
- `packages/vnpy-ashare/vnpy_ashare/config/schema.py`
- `packages/vnpy-ashare/vnpy_ashare/ui/shell/settings/dialog.py`
- `tests/ashare/test_config_apply.py`

---

## 参考

- [架构说明 §配置](./architecture.md#配置)
- [智能体投研团队 §深度模式](./team-agent.md#快速模式-vs-深度模式)
