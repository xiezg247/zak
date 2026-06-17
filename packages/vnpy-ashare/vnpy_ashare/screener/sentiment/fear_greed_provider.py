"""恐贪指数拉取注册表（打破 emotion_cycle_inputs ↔ services 循环）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_fetcher: Callable[..., Any | None] | None = None


def register_fear_greed_fetcher(fetcher: Callable[..., Any | None]) -> None:
    global _fetcher
    _fetcher = fetcher


def try_fetch_fear_greed_index(*, include_components: bool = False) -> Any | None:
    if _fetcher is None:
        return None
    try:
        return _fetcher(include_components=include_components)
    except Exception:
        return None
