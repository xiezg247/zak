"""终端 UI 偏好：本机 QSettings（flat 键），不写入 PG user_preferences。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_common.paths import SETTINGS_APP

T = TypeVar("T")

_json_cache: dict[str, Any] = {}

_LEGACY_UI_ORG = "vnpy_ashare"


def user_ui_settings_key(relative_key: str) -> str:
    """QSettings 键（flat，不含 user_id 前缀）。"""
    return relative_key.strip().strip("/")


def _uid_prefixed_key(relative_key: str, uid: str) -> str:
    rel = user_ui_settings_key(relative_key)
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


def _read_raw_local_ui(relative_key: str) -> object:
    rel = user_ui_settings_key(relative_key)
    if not rel:
        return None

    current = get_settings()
    raw = current.value(rel)
    if raw is not None:
        return raw

    uid_key = _uid_prefixed_key(rel, get_user_id())
    raw = current.value(uid_key)
    if raw is not None:
        return raw

    for org in (_LEGACY_UI_ORG,):
        legacy = QtCore.QSettings(org, SETTINGS_APP)
        raw = legacy.value(uid_key)
        if raw is not None:
            return raw
        raw = legacy.value(rel)
        if raw is not None:
            return raw

    return None


def load_json_local_ui(
    relative_key: str,
    *,
    load_default: Callable[[], T],
) -> T:
    ck = _cache_key(relative_key)
    if ck in _json_cache:
        return cast(T, _json_cache[ck])

    stored = _decode_json_value(_read_raw_local_ui(relative_key))
    if stored is not None:
        _json_cache[ck] = stored
        return cast(T, stored)

    legacy = load_default()
    _json_cache[ck] = legacy
    return legacy


def save_json_local_ui(relative_key: str, value: Any) -> None:
    ck = _cache_key(relative_key)
    _json_cache[ck] = value
    get_settings().setValue(
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
        return cast(T, _json_cache[ck])

    raw = _read_raw_local_ui(relative_key)
    if raw is not None:
        _json_cache[ck] = raw
        return cast(T, raw)

    legacy = load_default()
    _json_cache[ck] = legacy
    return legacy


def save_scalar_local_ui(relative_key: str, value: Any) -> None:
    ck = _cache_key(relative_key)
    _json_cache[ck] = value
    get_settings().setValue(user_ui_settings_key(relative_key), value)


def clear_local_ui_pref_cache() -> None:
    """测试或切换用户时清空进程内缓存。"""
    _json_cache.clear()
