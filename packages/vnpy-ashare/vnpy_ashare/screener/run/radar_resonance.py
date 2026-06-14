"""雷达共振选股执行。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.radar_models import RadarResonanceEntry
from vnpy_ashare.quotes.radar_resonance_store import (
    get_radar_resonance_entries,
    radar_resonance_updated_at,
)
from vnpy_ashare.screener.run.export import resolve_export_columns
from vnpy_ashare.screener.run.runner import ScreenerRunResult


def resonance_entries_to_rows(entries: tuple[RadarResonanceEntry, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        cards = "、".join(entry.card_titles)
        rows.append(
            {
                "symbol": entry.symbol,
                "name": entry.name,
                "vt_symbol": entry.vt_symbol,
                "last_price": entry.price or 0,
                "change_pct": entry.change_pct if entry.change_pct is not None else 0,
                "card_count": entry.card_count,
                "hit_reason": f"共振 {entry.card_count} 卡：{cards}",
                "source": "radar",
            }
        )
    return rows


def run_radar_resonance_screen(*, top_n: int = 50) -> ScreenerRunResult:
    entries = get_radar_resonance_entries()
    if not entries:
        raise RuntimeError("暂无雷达共振数据，请先打开雷达页刷新卡片。")
    top_n = max(1, min(int(top_n or 50), 200))
    sliced = entries[:top_n]
    rows = resonance_entries_to_rows(sliced)
    return ScreenerRunResult(
        rows=rows,
        condition="雷达共振",
        updated_at=radar_resonance_updated_at(),
        total_scanned=len(entries),
        source="radar",
        columns=resolve_export_columns(rows),
    )
