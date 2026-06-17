"""运行时配置分级热应用（保存 vt_setting / 从 .env 同步后调用）。"""

from __future__ import annotations

import logging
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import ConfigDict, Field
from vnpy.trader.setting import SETTINGS

from vnpy_ashare.app.engine_access import get_ashare_engine
from vnpy_ashare.config.datafeed_reload import reload_datafeed_stack
from vnpy_ashare.config.fonts import apply_app_font, resolve_font_family
from vnpy_ashare.config.schema import ENV_CONFIG_SPECS, VT_CONFIG_SPECS
from vnpy_ashare.config.vt_settings import reload_vnpy_settings
from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.scheduler.manager import TaskSchedulerManager
from vnpy_common.paths import ENV_FILE
from vnpy_common.ui.theme import theme_manager

ApplyTier = Literal["instant", "soft_reload", "restart_required"]

_INSTANT_VT_KEYS: frozenset[str] = frozenset({"log.active", "log.level", "font.family", "font.size"})
_SOFT_RELOAD_VT_KEYS: frozenset[str] = frozenset(
    {"datafeed.name", "datafeed.username", "datafeed.password"},
)
_RESTART_VT_PREFIXES: tuple[str, ...] = ("database.",)

_DATAFEED_ENV_KEYS: frozenset[str] = frozenset({"DATAFEED_NAME", "TICKFLOW_API_KEY", "TUSHARE_TOKEN"})

_INSTANT_ENV_KEYS: frozenset[str] = frozenset(spec.key for spec in ENV_CONFIG_SPECS if spec.group == "大模型")
_LLM_ENV_KEYS: frozenset[str] = _INSTANT_ENV_KEYS
_SOFT_RELOAD_ENV_KEYS: frozenset[str] = frozenset(
    {
        "DATAFEED_NAME",
        "TICKFLOW_API_KEY",
        "TUSHARE_TOKEN",
        "REDIS_URL",
        "QUOTE_COLLECT_INTERVAL",
    }
)
_RESTART_ENV_KEYS: frozenset[str] = frozenset(spec.key for spec in ENV_CONFIG_SPECS if spec.group in {"数据库", "PostgreSQL"} or spec.key == "DATABASE_NAME")
_NOTIFY_ENV_KEYS: frozenset[str] = frozenset(
    {"NOTIFY_ENABLED", "FEISHU_WEBHOOK_URL", "FEISHU_WEBHOOK_SECRET", "NOTIFY_MIN_INTERVAL_SEC"},
)

_VT_LABELS: dict[str, str] = {spec.key: spec.label for spec in VT_CONFIG_SPECS}
_ENV_LABELS: dict[str, str] = {spec.key: spec.label for spec in ENV_CONFIG_SPECS}


class ApplyResult(MutableModel):
    key: str = Field(description="配置键名")
    label: str = Field(description="展示标签")
    tier: ApplyTier = Field(description="应用分级")
    success: bool = Field(description="是否应用成功")
    message: str = Field(description="应用结果说明")


class ApplyContext(MutableModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_engine: Any | None = Field(default=None, description="LLM 引擎实例")
    scheduler: TaskSchedulerManager | None = Field(default=None, description="任务调度器")
    notification_service: Any | None = Field(default=None, description="通知服务实例")
    reload_env: bool = Field(default=False, description="是否重新加载环境变量")


def vt_apply_tier(key: str) -> ApplyTier:
    if key in _INSTANT_VT_KEYS:
        return "instant"
    if key in _SOFT_RELOAD_VT_KEYS:
        return "soft_reload"
    if any(key.startswith(prefix) for prefix in _RESTART_VT_PREFIXES):
        return "restart_required"
    return "restart_required"


def env_apply_tier(key: str) -> ApplyTier:
    if key in _INSTANT_ENV_KEYS or key in _NOTIFY_ENV_KEYS:
        return "instant"
    if key in _SOFT_RELOAD_ENV_KEYS:
        return "soft_reload"
    if key in _RESTART_ENV_KEYS:
        return "restart_required"
    return "soft_reload"


def label_for_key(key: str) -> str:
    return _VT_LABELS.get(key) or _ENV_LABELS.get(key) or key


def diff_settings(previous: dict, updates: dict) -> dict:
    """返回相对 previous 实际变更的键值。"""
    changed: dict = {}
    for key, value in updates.items():
        if previous.get(key) != value:
            changed[key] = value
    return changed


def build_apply_context(parent: Any | None) -> ApplyContext:
    """从配置对话框 parent（MainWindow）构建 ApplyContext。"""
    ctx = ApplyContext()
    if parent is None:
        return ctx
    if hasattr(parent, "_get_llm_engine"):
        ctx.llm_engine = parent._get_llm_engine()
    main_engine = getattr(parent, "main_engine", None)
    if main_engine is not None:

        ashare = get_ashare_engine(main_engine)
        if ashare is not None:
            ctx.scheduler = ashare.scheduler
            ctx.notification_service = ashare.notification_service
    return ctx


def apply_runtime_settings(
    changed: dict,
    *,
    context: ApplyContext | None = None,
) -> list[ApplyResult]:
    """对已持久化的 vt_setting 变更项分级应用。"""
    if not changed:
        return []

    reload_vnpy_settings()

    tiers_present = {vt_apply_tier(key) for key in changed}
    results: list[ApplyResult] = []

    if "instant" in tiers_present:
        results.extend(_apply_instant_vt(changed))
    if "soft_reload" in tiers_present:
        results.extend(_apply_soft_vt(changed))
    if "restart_required" in tiers_present:
        results.extend(_apply_restart_vt(changed))

    return results


def apply_env_side_effects(
    changed_env_keys: set[str] | frozenset[str],
    *,
    context: ApplyContext | None = None,
) -> list[ApplyResult]:
    """`.env` 变更或「从 .env 同步」后的副作用（LLM 重载等）。"""
    if not changed_env_keys:
        return []



    if ENV_FILE.is_file():
        load_dotenv(ENV_FILE, override=True)

    ctx = context or ApplyContext()
    results: list[ApplyResult] = []

    if changed_env_keys & _LLM_ENV_KEYS:
        results.append(_apply_llm_reload(ctx))

    if changed_env_keys & _NOTIFY_ENV_KEYS:
        results.append(_apply_notify_reload(ctx))

    datafeed_env_changed = bool(changed_env_keys & _DATAFEED_ENV_KEYS)
    datafeed_ok = True
    datafeed_message = ""
    if datafeed_env_changed:
        datafeed_ok, datafeed_message = _reload_datafeed_stack()

    for key in sorted(changed_env_keys):
        tier = env_apply_tier(key)
        if tier == "soft_reload":
            if key in _DATAFEED_ENV_KEYS and datafeed_env_changed:
                message = datafeed_message or "已重新加载环境变量"
                success = datafeed_ok
            else:
                message = "已重新加载环境变量"
                success = True
            results.append(
                ApplyResult(
                    key=key,
                    label=label_for_key(key),
                    tier="soft_reload",
                    success=success,
                    message=message,
                )
            )
        elif tier == "restart_required":
            results.append(
                ApplyResult(
                    key=key,
                    label=label_for_key(key),
                    tier="restart_required",
                    success=True,
                    message="已同步，需重启应用后生效",
                )
            )

    return results


def apply_llm_reload(context: ApplyContext | None = None) -> ApplyResult:
    """手动或保存后重载 LLM 配置。"""
    return _apply_llm_reload(context or ApplyContext())


def format_apply_summary(path: str, results: list[ApplyResult]) -> str:
    lines = [f"配置已写入 {path}"]
    for item in results:
        prefix = "✓" if item.tier != "restart_required" and item.success else "⚠"
        if item.tier == "restart_required":
            prefix = "⚠"
        lines.append(f"{prefix} {item.label} — {item.message}")
    return "\n".join(lines)


def format_env_sync_summary(path: str, results: list[ApplyResult]) -> str:
    lines = [f"已从 .env 写入 {path}"]
    for item in results:
        prefix = "✓" if item.success and item.tier != "restart_required" else "⚠"
        if item.tier == "restart_required":
            prefix = "⚠"
        lines.append(f"{prefix} {item.label} — {item.message}")
    return "\n".join(lines)


def format_combined_save_summary(
    *,
    env_path: str | None,
    runtime_path: str | None,
    results: list[ApplyResult],
) -> str:
    lines: list[str] = []
    if env_path:
        lines.append(f"环境变量已写入 {env_path}")
    if runtime_path:
        lines.append(f"运行时配置已写入 {runtime_path}")
    if not lines:
        lines.append("配置已保存")
    for item in results:
        prefix = "✓" if item.tier != "restart_required" and item.success else "⚠"
        if item.tier == "restart_required":
            prefix = "⚠"
        lines.append(f"{prefix} {item.label} — {item.message}")
    return "\n".join(lines)


def _apply_instant_vt(changed: dict) -> list[ApplyResult]:
    results: list[ApplyResult] = []
    log_keys = [key for key in changed if key in {"log.active", "log.level"}]
    font_keys = [key for key in changed if key in {"font.family", "font.size"}]

    log_ok = True
    if log_keys:
        log_ok = _apply_log_settings()

    font_ok = True
    if font_keys:
        font_ok = _apply_font_settings()

    for key in changed:
        if vt_apply_tier(key) != "instant":
            continue
        if key in {"log.active", "log.level"}:
            success = log_ok
        else:
            success = font_ok
        results.append(
            ApplyResult(
                key=key,
                label=label_for_key(key),
                tier="instant",
                success=success,
                message="已立即生效" if success else "应用失败",
            )
        )
    return results


def _apply_soft_vt(changed: dict) -> list[ApplyResult]:
    soft_keys = [key for key in changed if vt_apply_tier(key) == "soft_reload"]
    if not soft_keys:
        return []

    ok, stack_message = _reload_datafeed_stack()
    message = stack_message if ok else stack_message
    return [
        ApplyResult(
            key=key,
            label=label_for_key(key),
            tier="soft_reload",
            success=ok,
            message=message,
        )
        for key in soft_keys
    ]


def _apply_restart_vt(changed: dict) -> list[ApplyResult]:
    return [
        ApplyResult(
            key=key,
            label=label_for_key(key),
            tier="restart_required",
            success=True,
            message="已保存，需重启应用后生效",
        )
        for key in changed
        if vt_apply_tier(key) == "restart_required"
    ]


def _reload_datafeed_stack() -> tuple[bool, str]:

    return reload_datafeed_stack()


def _apply_log_settings() -> bool:
    try:
        active = SETTINGS.get("log.active", True)
        level_name = str(SETTINGS.get("log.level", "INFO")).upper()
        level = getattr(logging, level_name, logging.INFO)
        root = logging.getLogger()
        if active in (False, "false", "0", 0):
            root.setLevel(logging.CRITICAL + 1)
        else:
            root.setLevel(level)
        return True
    except Exception:
        return False


def _apply_font_settings() -> bool:
    try:

        SETTINGS["font.family"] = resolve_font_family(SETTINGS.get("font.family"))
        SETTINGS["font.size"] = int(SETTINGS.get("font.size", 12))
        if not apply_app_font():
            return False

        theme_manager().apply()
        return True
    except Exception:
        return False


def _apply_llm_reload(ctx: ApplyContext) -> ApplyResult:
    key = "LLM_API_KEY"
    if ctx.llm_engine is None:
        return ApplyResult(
            key=key,
            label="大模型",
            tier="instant",
            success=False,
            message="LLM 引擎未加载",
        )
    try:
        cfg = ctx.llm_engine.reload_config()
    except Exception as exc:
        return ApplyResult(
            key=key,
            label="大模型",
            tier="instant",
            success=False,
            message=f"重载失败：{exc}",
        )
    if cfg.configured:
        return ApplyResult(
            key=key,
            label="大模型",
            tier="instant",
            success=True,
            message=f"已重载：{cfg.model} · {cfg.api_base}",
        )
    return ApplyResult(
        key=key,
        label="大模型",
        tier="instant",
        success=False,
        message="未检测到 LLM_API_KEY",
    )


def _apply_notify_reload(ctx: ApplyContext) -> ApplyResult:
    key = "NOTIFY_ENABLED"
    service = ctx.notification_service
    if service is None:
        return ApplyResult(
            key=key,
            label="消息通知",
            tier="instant",
            success=True,
            message="已写入 .env（下次启动引擎后生效）",
        )
    try:
        service.reload()
    except Exception as exc:
        return ApplyResult(
            key=key,
            label="消息通知",
            tier="instant",
            success=False,
            message=f"重载失败：{exc}",
        )
    return ApplyResult(
        key=key,
        label="消息通知",
        tier="instant",
        success=True,
        message="通知配置已重载",
    )
