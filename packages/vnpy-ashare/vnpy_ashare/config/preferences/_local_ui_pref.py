"""终端 UI 偏好：本机 QSettings（按 user_id 隔离），不写入 PG user_preferences。"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.storage.auth.scope import get_user_id

T = TypeVar("T")

_json_cache: dict[str, Any] = {}
_bootstrap_done_for_user: str | None = None


@dataclass(frozen=True)
class UiPgPrefSpec:
    namespace: str
    pg_key: str
    local_key: str
    kind: Literal["json", "scalar"]


# 历史上误入 PG 的纯 UI 键；登录 bootstrap 后必须从 PG 删除。
UI_PG_PREF_SPECS: tuple[UiPgPrefSpec, ...] = (
    UiPgPrefSpec("watchlist", "signal_panel", "watchlist/signal_panel", "json"),
    UiPgPrefSpec("watchlist", "position_panel", "watchlist/position_panel", "json"),
    UiPgPrefSpec("watchlist", "active_group_id", "watchlist/active_group_id", "scalar"),
    UiPgPrefSpec("watchlist", "center_splitter_sizes", "watchlist/center_splitter_sizes", "json"),
    UiPgPrefSpec("watchlist", "stale_sweep_minutes", "watchlist/stale_sweep_minutes", "scalar"),
    UiPgPrefSpec("radar", "full_refresh_every", "radar/full_refresh_every", "json"),
    UiPgPrefSpec("llm", "nl_screening_confirm_enabled", "llm/nl_screening_confirm_enabled", "scalar"),
)


def user_ui_settings_key(relative_key: str) -> str:
    rel = relative_key.strip().strip("/")
    uid = get_user_id()
    return f"ui/{uid}/{rel}" if rel else f"ui/{uid}"


def _cache_key(relative_key: str) -> str:
    return user_ui_settings_key(relative_key)


def _decode_json_value(raw: object) -> Any | None:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _local_ui_has_value(relative_key: str, *, kind: Literal["json", "scalar"]) -> bool:
    settings = get_settings()
    raw = settings.value(user_ui_settings_key(relative_key))
    if raw is None:
        return False
    if kind == "json":
        return _decode_json_value(raw) is not None
    return str(raw).strip() != ""


def purge_ui_prefs_from_pg() -> int:
    """删除 PG 中所有纯 UI 偏好行。"""
    from vnpy_ashare.storage.auth.preferences import delete_prefs

    keys = [(spec.namespace, spec.pg_key) for spec in UI_PG_PREF_SPECS]
    return delete_prefs(keys)


def bootstrap_local_ui_prefs_from_pg() -> None:
    """登录后：PG→本地（仅本地缺失时），然后清除 PG 中的 UI 键。"""
    global _bootstrap_done_for_user

    uid = get_user_id()
    if _bootstrap_done_for_user == uid:
        return
    _bootstrap_done_for_user = uid

    from vnpy_ashare.storage.auth.preferences import get_pref

    for spec in UI_PG_PREF_SPECS:
        pg_value = get_pref(spec.namespace, spec.pg_key, None)
        if pg_value is None:
            continue
        if _local_ui_has_value(spec.local_key, kind=spec.kind):
            continue
        if spec.kind == "json":
            save_json_local_ui(spec.local_key, pg_value)
        else:
            save_scalar_local_ui(spec.local_key, pg_value)

    purge_ui_prefs_from_pg()


def load_json_local_ui(
    relative_key: str,
    *,
    load_default: Callable[[], T],
) -> T:
    ck = _cache_key(relative_key)
    if ck in _json_cache:
        return _json_cache[ck]  # type: ignore[return-value]

    settings = get_settings()
    stored = _decode_json_value(settings.value(user_ui_settings_key(relative_key)))
    if stored is not None:
        _json_cache[ck] = stored
        return stored  # type: ignore[return-value]

    legacy = load_default()
    _json_cache[ck] = legacy
    return legacy


def save_json_local_ui(relative_key: str, value: Any) -> None:
    ck = _cache_key(relative_key)
    _json_cache[ck] = value
    settings = get_settings()
    settings.setValue(
        user_ui_settings_key(relative_key),
        json.dumps(value, ensure_ascii=False),
    )


def load_scalar_local_ui(
    relative_key: str,
    *,
    load_default: Callable[[], T],
) -> T:
    ck = _cache_key(relative_key)
    if ck in _json_cache:
        return _json_cache[ck]  # type: ignore[return-value]

    settings = get_settings()
    raw = settings.value(user_ui_settings_key(relative_key))
    if raw is not None:
        _json_cache[ck] = raw
        return raw  # type: ignore[return-value]

    legacy = load_default()
    _json_cache[ck] = legacy
    return legacy


def save_scalar_local_ui(relative_key: str, value: Any) -> None:
    ck = _cache_key(relative_key)
    _json_cache[ck] = value
    get_settings().setValue(user_ui_settings_key(relative_key), value)


def clear_local_ui_pref_cache() -> None:
    """测试或切换用户时清空进程内缓存。"""
    global _bootstrap_done_for_user

    _json_cache.clear()
    _bootstrap_done_for_user = None
