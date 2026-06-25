"""用户业务偏好 PG 读写与 QSettings 懒迁移辅助。

纯 UI 壳层偏好请使用 config.preferences._local_ui_pref，不要经本模块写入 PG。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.storage.auth.preferences import get_pref, set_pref

T = TypeVar("T")


def qsettings_has_keys(keys: tuple[str, ...]) -> bool:
    settings = get_settings()
    return any(settings.value(key) is not None for key in keys)


def qsettings_contains(key: str) -> bool:
    return bool(get_settings().contains(key))


def load_model_pref(
    namespace: str,
    pref_key: str,
    model_type: type[BaseModel],
    *,
    load_legacy: Callable[[], BaseModel],
    migrate_keys: tuple[str, ...] = (),
) -> BaseModel:
    stored = get_pref(namespace, pref_key, None)
    if stored is not None:
        return model_type.model_validate(stored)
    legacy = load_legacy()
    if migrate_keys and qsettings_has_keys(migrate_keys):
        set_pref(namespace, pref_key, legacy.model_dump())
    return legacy


def save_model_pref(namespace: str, pref_key: str, model: BaseModel) -> None:
    set_pref(namespace, pref_key, model.model_dump())


def load_json_pref(
    namespace: str,
    pref_key: str,
    *,
    load_legacy: Callable[[], T],
    migrate_keys: tuple[str, ...] = (),
) -> T:
    stored = get_pref(namespace, pref_key, None)
    if stored is not None:
        return stored  # type: ignore[return-value]
    legacy = load_legacy()
    if migrate_keys and qsettings_has_keys(migrate_keys):
        set_pref(namespace, pref_key, legacy)
    return legacy


def save_json_pref(namespace: str, pref_key: str, value: Any) -> None:
    set_pref(namespace, pref_key, value)


def load_scalar_pref(
    namespace: str,
    pref_key: str,
    *,
    load_legacy: Callable[[], T],
    migrate_key: str = "",
) -> T:
    stored = get_pref(namespace, pref_key, None)
    if stored is not None:
        return stored  # type: ignore[return-value]
    legacy = load_legacy()
    if migrate_key and (qsettings_has_keys((migrate_key,)) or qsettings_contains(migrate_key)):
        set_pref(namespace, pref_key, legacy)
    return legacy


def save_scalar_pref(namespace: str, pref_key: str, value: Any) -> None:
    set_pref(namespace, pref_key, value)
