"""雷达共振快照（供策略选股页读取）。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from vnpy_ashare.quotes.radar_models import RadarResonanceEntry

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

_entries: tuple[RadarResonanceEntry, ...] = ()
_updated_at: str | None = None


def set_radar_resonance_entries(entries: tuple[RadarResonanceEntry, ...]) -> None:
    global _entries, _updated_at
    _entries = tuple(entries)
    _updated_at = datetime.now(_SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")


def get_radar_resonance_entries() -> tuple[RadarResonanceEntry, ...]:
    return _entries


def radar_resonance_updated_at() -> str | None:
    return _updated_at
