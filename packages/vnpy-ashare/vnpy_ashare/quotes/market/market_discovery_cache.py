"""市场页异动带进程内 TTL 缓存（盘后展示上次盘中结果）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.quotes.core.cache_ttl import TtlCache

if TYPE_CHECKING:
    from vnpy_ashare.quotes.radar.loaders import RadarCardData

_INTRADAY_TTL_SEC = 60.0
_OFF_SESSION_TTL_SEC = 86400.0

_discovery_cache: TtlCache[tuple[RadarCardData | None, RadarCardData | None]] = TtlCache()


def peek_discovery_cards(*, intraday: bool) -> tuple[RadarCardData | None, RadarCardData | None] | None:
    ttl = _INTRADAY_TTL_SEC if intraday else _OFF_SESSION_TTL_SEC
    return _discovery_cache.peek(max_age_sec=ttl)


def store_discovery_cards(
    volume: RadarCardData | None,
    moneyflow: RadarCardData | None,
) -> None:
    _discovery_cache.store((volume, moneyflow))


def invalidate_discovery_cache() -> None:
    _discovery_cache.invalidate()
