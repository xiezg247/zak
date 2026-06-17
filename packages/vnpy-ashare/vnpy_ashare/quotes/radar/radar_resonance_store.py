"""雷达共振快照（供策略选股页读取）。"""

from __future__ import annotations

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.quotes.radar.radar_models import RadarResonanceEntry

_entries: tuple[RadarResonanceEntry, ...] = ()
_updated_at: str | None = None


def set_radar_resonance_entries(entries: tuple[RadarResonanceEntry, ...]) -> None:
    global _entries, _updated_at
    _entries = tuple(entries)
    _updated_at = format_china_datetime()


def get_radar_resonance_entries() -> tuple[RadarResonanceEntry, ...]:
    return _entries


def radar_resonance_updated_at() -> str | None:
    return _updated_at
