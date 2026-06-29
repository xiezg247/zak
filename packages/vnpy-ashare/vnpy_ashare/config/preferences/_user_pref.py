"""用户业务偏好 PG 读写。

纯 UI 壳层偏好请使用 config.preferences._local_ui_pref，不要经本模块写入 PG。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from vnpy_ashare.storage.auth.preferences import get_pref, set_pref

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


def load_model_pref(
    namespace: str,
    pref_key: str,
    model_type: type[M],
    *,
    load_default: Callable[[], M],
) -> M:
    stored = get_pref(namespace, pref_key, None)
    if stored is not None:
        return model_type.model_validate(stored)
    return load_default()


def save_model_pref(namespace: str, pref_key: str, model: BaseModel) -> None:
    set_pref(namespace, pref_key, model.model_dump())


def load_json_pref(
    namespace: str,
    pref_key: str,
    *,
    load_default: Callable[[], T],
) -> T:
    stored = get_pref(namespace, pref_key, None)
    if stored is not None:
        return cast(T, stored)
    return load_default()


def save_json_pref(namespace: str, pref_key: str, value: Any) -> None:
    set_pref(namespace, pref_key, value)


def load_scalar_pref(
    namespace: str,
    pref_key: str,
    *,
    load_default: Callable[[], T],
) -> T:
    stored = get_pref(namespace, pref_key, None)
    if stored is not None:
        return cast(T, stored)
    return load_default()


def save_scalar_pref(namespace: str, pref_key: str, value: Any) -> None:
    set_pref(namespace, pref_key, value)
