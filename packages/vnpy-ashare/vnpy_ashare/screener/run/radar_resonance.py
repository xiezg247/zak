"""雷达共振选股执行。"""

from __future__ import annotations

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.quotes.radar.radar_models import RadarResonanceEntry
from vnpy_ashare.quotes.radar.radar_resonance_store import (
    get_radar_resonance_entries,
    radar_resonance_updated_at,
)
from vnpy_ashare.screener.run.result import ScreenerRunResult, build_screener_run_result


def resonance_entries_to_result_rows(entries: tuple[RadarResonanceEntry, ...]) -> list[ScreenerResultRow]:
    rows: list[ScreenerResultRow] = []
    for entry in entries:
        cards = "、".join(entry.card_titles)
        score = entry.resonance_score
        score_text = f"加权{score:.1f}" if score > 0 else f"{entry.card_count}卡"
        rows.append(
            ScreenerResultRow.from_mapping(
                {
                    "symbol": entry.symbol,
                    "name": entry.name,
                    "vt_symbol": entry.vt_symbol,
                    "last_price": entry.price or 0,
                    "change_pct": entry.change_pct if entry.change_pct is not None else 0,
                    "card_count": entry.card_count,
                    "resonance_score": score,
                    "hit_reason": f"共振 {score_text}：{cards}",
                    "source": "radar",
                }
            )
        )
    return rows


def run_radar_resonance_screen(*, top_n: int = 50) -> ScreenerRunResult:
    entries = get_radar_resonance_entries()
    if not entries:
        raise RuntimeError("暂无雷达共振数据，请先打开雷达页刷新卡片。")
    top_n = max(1, min(int(top_n or 50), 200))
    sliced = entries[:top_n]
    rows = resonance_entries_to_result_rows(sliced)
    return build_screener_run_result(
        rows=rows,
        condition="雷达共振",
        updated_at=radar_resonance_updated_at(),
        total_scanned=len(entries),
        source="radar",
    )
