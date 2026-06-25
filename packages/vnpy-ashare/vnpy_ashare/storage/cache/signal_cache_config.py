"""信号/持仓 cache backend 配置。"""

from __future__ import annotations

import os

from vnpy_common.paths import ENV_FILE

_VALID_BACKENDS = frozenset({"redis", "pg", "memory"})


def resolve_signal_cache_backend() -> str:
    """ZAK_SIGNAL_CACHE_BACKEND：redis（默认）| pg | memory。"""
    raw = os.getenv("ZAK_SIGNAL_CACHE_BACKEND", "redis").strip().lower()
    if raw in _VALID_BACKENDS:
        return raw
    return "redis"


def signal_cache_ttl_seconds() -> int:
    """Redis key TTL；默认 24h。"""
    raw = os.getenv("ZAK_SIGNAL_CACHE_TTL_SEC", "").strip()
    if raw.isdigit():
        return max(60, int(raw))
    return 86400


def l1_cache_ttl_seconds() -> float:
    """进程内 L1 TTL；默认 1.5s，适合 UI 高频 refresh。"""
    raw = os.getenv("ZAK_SIGNAL_CACHE_L1_SEC", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return 1.5


def ensure_env_loaded() -> None:
    if not os.getenv("_ZAK_ENV_LOADED"):
        from dotenv import load_dotenv

        load_dotenv(ENV_FILE)
