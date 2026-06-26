"""性能预设 env 填充。"""

from __future__ import annotations

import os

import tests._bootstrap  # noqa: F401
from vnpy_common.perf_profile import apply_perf_profile_from_env, perf_profile_defaults, resolve_perf_profile


def _clear_perf_env() -> dict[str, str | None]:
    keys = [
        "ZAK_PERF_PROFILE",
        "ZAK_QUOTE_L1_CACHE",
        "ZAK_COLLECT_DEFER_ENRICH",
        "ZAK_QUOTE_REDIS_NOTIFY",
        "ZAK_RANK_PRECOMPUTE",
        "ZAK_RANK_ORDERED_LIST",
        "ZAK_RANK_INCREMENTAL",
        "ZAK_REDIS_QUOTE_COMPACT",
        "ZAK_REDIS_QUOTE_BLOB",
    ]
    saved = {key: os.environ.pop(key, None) for key in keys}
    return saved


def _restore_perf_env(saved: dict[str, str | None]) -> None:
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_resolve_perf_profile_aliases() -> None:
    assert resolve_perf_profile("leader") == "leader"
    assert resolve_perf_profile("gui") == "client"
    assert resolve_perf_profile("") == "off"


def test_leader_profile_fills_missing_keys() -> None:
    saved = _clear_perf_env()
    try:
        os.environ["ZAK_PERF_PROFILE"] = "leader"
        profile = apply_perf_profile_from_env()
        assert profile == "leader"
        assert os.environ["ZAK_QUOTE_L1_CACHE"] == "1"
        assert os.environ["ZAK_REDIS_QUOTE_BLOB"] == "1"
    finally:
        _restore_perf_env(saved)


def test_explicit_env_overrides_profile() -> None:
    saved = _clear_perf_env()
    try:
        os.environ["ZAK_PERF_PROFILE"] = "leader"
        os.environ["ZAK_QUOTE_L1_CACHE"] = "0"
        apply_perf_profile_from_env()
        assert os.environ["ZAK_QUOTE_L1_CACHE"] == "0"
        assert os.environ["ZAK_COLLECT_DEFER_ENRICH"] == "1"
    finally:
        _restore_perf_env(saved)


def test_client_profile_smaller_set() -> None:
    defaults = perf_profile_defaults("client")
    assert "ZAK_QUOTE_L1_CACHE" not in defaults
    assert defaults["ZAK_QUOTE_REDIS_NOTIFY"] == "1"
