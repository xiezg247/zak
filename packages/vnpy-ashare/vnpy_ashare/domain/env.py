"""环境变量解析（RECIPE_* 等，环境变量优先于 QSettings）。"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_FALSE_VALUES = frozenset({"0", "false", "no"})


def env_str(key: str) -> str:
    return os.getenv(key, "").strip()


def env_bool(key: str) -> bool | None:
    """有设置时解析为 bool；未设置返回 None。"""
    raw = env_str(key)
    if not raw:
        return None
    return raw.lower() not in _FALSE_VALUES


def env_float(key: str, *, default: float) -> float | None:
    """有设置时解析为 float；未设置返回 None。"""
    raw = env_str(key)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return default


def env_int(key: str, *, default: int) -> int | None:
    raw = env_str(key)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return default


def env_or_prefs_bool(key: str, *, prefs: Callable[[], bool]) -> bool:
    override = env_bool(key)
    if override is not None:
        return override
    return prefs()


def env_or_prefs_float(
    key: str,
    *,
    default: float,
    prefs: Callable[[], float],
    clamp: tuple[float, float] | None = None,
) -> float:
    override = env_float(key, default=default)
    if override is not None and env_str(key):
        value = override
    else:
        value = prefs()
    if clamp is not None:
        lo, hi = clamp
        return max(lo, min(hi, value))
    return value


def env_or_prefs_int(key: str, *, default: int, prefs: Callable[[], int]) -> int:
    override = env_int(key, default=default)
    if override is not None and env_str(key):
        return max(0, override)
    return prefs()


def env_or_prefs_nonneg_float(key: str, *, default: float, prefs: Callable[[], float]) -> float:
    raw = env_str(key)
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return default
    return prefs()


def env_or_prefs_nonneg_int(key: str, *, default: int, prefs: Callable[[], int]) -> int:
    raw = env_str(key)
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            return default
    return prefs()


def env_or_prefs_str(key: str, *, prefs: Callable[[], str]) -> str:
    raw = env_str(key)
    if raw:
        return raw
    return prefs()
