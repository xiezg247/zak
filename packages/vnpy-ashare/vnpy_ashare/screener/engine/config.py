"""选股引擎配置（``ZAK_SCREENER_ENGINE=polars|python``）。"""

from __future__ import annotations

import os

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def screener_engine() -> str:
    raw = os.environ.get("ZAK_SCREENER_ENGINE", "python").strip().lower()
    return "polars" if raw == "polars" else "python"


def polars_engine_enabled() -> bool:
    return screener_engine() == "polars"


def polars_available() -> bool:
    try:
        import polars  # noqa: F401

        return True
    except ImportError:
        return False
