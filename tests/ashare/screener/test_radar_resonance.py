"""雷达共振选股单元测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.quotes.radar.radar_models import RadarResonanceEntry
from vnpy_ashare.quotes.radar.radar_resonance_store import (
    get_radar_resonance_entries,
    set_radar_resonance_entries,
)
from vnpy_ashare.screener.run.radar_resonance import (
    resonance_entries_to_rows,
    run_radar_resonance_screen,
)


def _entry(symbol: str, *, card_count: int = 2) -> RadarResonanceEntry:
    return RadarResonanceEntry(
        vt_symbol=f"{symbol}.SSE",
        name=symbol,
        symbol=symbol,
        card_count=card_count,
        card_titles=("动量", "板块"),
        price=10.0,
        change_pct=5.0,
    )


def test_resonance_entries_to_rows_includes_hit_reason():
    rows = resonance_entries_to_rows((_entry("AAA"),))
    assert rows[0]["symbol"] == "AAA"
    assert "共振 2" in rows[0]["hit_reason"]
    assert rows[0]["source"] == "radar"


def test_run_radar_resonance_screen_requires_snapshot():
    set_radar_resonance_entries(())
    with pytest.raises(RuntimeError, match="暂无雷达共振数据"):
        run_radar_resonance_screen()


def test_run_radar_resonance_screen_returns_sorted_slice():
    entries = (_entry("B", card_count=3), _entry("A", card_count=2))
    set_radar_resonance_entries(entries)
    result = run_radar_resonance_screen(top_n=1)
    assert result.condition == "雷达共振"
    assert result.source == "radar"
    assert len(result.rows) == 1
    assert result.rows[0]["symbol"] == "B"
    assert result.total_scanned == 2
    assert get_radar_resonance_entries() == entries
