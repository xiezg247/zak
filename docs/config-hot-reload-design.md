# 配置页分级热加载设计

## 背景

zak 已有系统配置页（`ui/shell/settings/`），配置分两层：

| 层 | 文件 | 用途 |
|----|------|------|
| 环境变量 | `.env` | 密钥与基础设施（TickFlow、Tushare、Redis、LLM、PG 连接等） |
| 运行时 | `vt_setting.json` | VeighNa `SETTINGS` 镜像（字体、日志、datafeed、K 线库等） |

此前保存后统一提示「需重启」，仅 LLM 提供手动「重载 LLM」按钮。用户改日志级别、数据源等低风险项也被迫重启，体验差；而 K 线库切换、字体等高风险项若强行热加载易出隐蔽 bug。

**目标**：配置页统一入口不变，保存后按配置项**分级反馈**并**尽力热应用**，无法安全热加载的项明确标注需重启。

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

保存时写入 `.env` 并调用 `apply_env_side_effects`（LLM / datafeed / Redis 等分级 apply）。若需同步到 `vt_setting.json`，仍使用「从 .env 同步」。

| 配置项 | 档位 | 行为 |
|--------|------|------|
| `LLM_API_*` | **即时** | `load_dotenv` + `LlmEngine.reload_config()` |
| `DATAFEED_NAME` / `TICKFLOW_*` / `TUSHARE_*` | **软重载** | 同步写入 vt_setting 后合并 SETTINGS |
| `DATABASE_NAME` / `POSTGRES_*` | **需重启** | 同步后标注重启 |
| `REDIS_URL` / `QUOTE_COLLECT_INTERVAL` | **软重载** | 进程内 `load_dotenv`；采集任务下次调度读新 env（scheduler 间隔以 `*_scheduler.json` 为准） |

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
        ├── reload_vnpy_settings()          # 一次合并 vt_setting → SETTINGS
        ├── instant  → _apply_log_settings() / _apply_font_settings()
        ├── soft     → reload_datafeed_stack()
        ├── restart  → 仅结果文案
        └── context.llm_engine → reload_config()（sync / 手动重载）
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

`ApplyContext` 注入可选依赖：

- `llm_engine`：AI 助手重载
- `scheduler`：预留；当前 scheduler 间隔不读 `.env`，后续可扩展

### UX 规范

保存/同步成功后，通知按项列出（最多展示变更项）：

```
配置已写入 ~/.vntrader/vt_setting.json
✓ 日志级别 — 已立即生效
✓ 数据源 — 已更新全局 SETTINGS
⚠ 字体 — 已保存，需重启应用后生效
```

- 全部即时/软重载 → `success`
- 含需重启项 → 仍 `success`，文案含 ⚠
- 应用失败（如 LLM 未配置）→ 对应行 warning，不阻断保存

顶栏 hint 改为说明分级策略，保留「重载 LLM」作手动兜底。

## 实施阶段

P1–P4 均已完成（2026-06）。

| 阶段 | 内容 | 状态 |
|------|------|------|
| P1 | `config/apply.py` + 保存/同步接入 + 单元测试 | 已完成 |
| P2 | datafeed 连接池显式重建（MainEngine） | 已完成 |
| P3 | 字体运行时刷新（theme_manager 广播） | 已完成 |
| P4 | `.env` 页内编辑（仍走分级 apply） | 已完成 |

## 相关文件

- `packages/vnpy-ashare/vnpy_ashare/config/env_store.py` — `.env` 持久化
- `packages/vnpy-ashare/vnpy_ashare/config/datafeed_reload.py` — vnpy datafeed 单例重建
- `packages/vnpy-ashare/vnpy_ashare/config/apply.py` — 分级应用
- `packages/vnpy-ashare/vnpy_ashare/config/schema.py` — 配置项定义
- `packages/vnpy-ashare/vnpy_ashare/ui/shell/settings/dialog.py` — 配置 UI
- `tests/ashare/test_config_apply.py` — 应用逻辑测试
