"""性能优化 env 预设（``ZAK_PERF_PROFILE``）。

显式设置的 ``ZAK_*`` 键优先于 profile 默认值。
"""

from __future__ import annotations

import os
from typing import Final

PROFILE_ENV_KEY: Final[str] = "ZAK_PERF_PROFILE"

_PROFILE_ALIASES: dict[str, str] = {
    "": "off",
    "off": "off",
    "0": "off",
    "false": "off",
    "client": "client",
    "gui": "client",
    "reader": "client",
    "leader": "leader",
    "collect": "leader",
}

_PROFILE_DEFAULTS: dict[str, dict[str, str]] = {
    "client": {
        "ZAK_QUOTE_REDIS_NOTIFY": "1",
        "ZAK_RANK_PRECOMPUTE": "1",
        "ZAK_RANK_ORDERED_LIST": "1",
        "ZAK_RANK_INCREMENTAL": "1",
        "ZAK_REDIS_QUOTE_BLOB": "1",
    },
    "leader": {
        "ZAK_QUOTE_L1_CACHE": "1",
        "ZAK_COLLECT_DEFER_ENRICH": "1",
        "ZAK_QUOTE_REDIS_NOTIFY": "1",
        "ZAK_RANK_PRECOMPUTE": "1",
        "ZAK_RANK_ORDERED_LIST": "1",
        "ZAK_RANK_INCREMENTAL": "1",
        "ZAK_REDIS_QUOTE_COMPACT": "1",
        "ZAK_REDIS_QUOTE_BLOB": "1",
    },
}


def resolve_perf_profile(raw: str | None = None) -> str:
    text = (raw if raw is not None else os.environ.get(PROFILE_ENV_KEY, "")).strip().lower()
    return _PROFILE_ALIASES.get(text, "off")


def perf_profile_defaults(profile: str | None = None) -> dict[str, str]:
    name = resolve_perf_profile(profile)
    return dict(_PROFILE_DEFAULTS.get(name, {}))


def apply_perf_profile_from_env() -> str:
    """根据 ``ZAK_PERF_PROFILE`` 填充未显式设置的性能相关 env。"""
    profile = resolve_perf_profile()
    for key, value in perf_profile_defaults(profile).items():
        if not os.environ.get(key, "").strip():
            os.environ[key] = value
    return profile

