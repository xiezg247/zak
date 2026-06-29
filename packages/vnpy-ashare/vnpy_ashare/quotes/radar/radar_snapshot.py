"""雷达全页快照构建。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.radar.card import RadarCardData, RadarResonanceEntry, RadarRow
from vnpy_ashare.domain.radar.snapshot import RadarBoardSnapshot, RadarLimitLadderSummary
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.loaders import build_radar_resonance_list

__all__ = [
    "build_radar_board_snapshot",
    "enrich_resonance_entries",
    "resonance_entry_to_row_dict",
    "row_lookup_from_payload",
]


def enrich_resonance_entries(
    entries: tuple[RadarResonanceEntry, ...],
    payload: dict[str, RadarCardData],
) -> tuple[RadarResonanceEntry, ...]:
    """为共振项补全 leader_tier / leader_score / limit_times。"""
    if not entries:
        return ()
    lookup = row_lookup_from_payload(payload)
    enriched: list[RadarResonanceEntry] = []
    for entry in entries:
        row = lookup.get(entry.vt_symbol)
        if row is None:
            enriched.append(entry)
            continue
        enriched.append(
            entry.model_copy(
                update={
                    "leader_tier": row.leader_tier or entry.leader_tier,
                    "leader_score": row.leader_score if row.leader_score is not None else entry.leader_score,
                    "limit_times": row.limit_times if row.limit_times is not None else entry.limit_times,
                }
            )
        )
    return tuple(enriched)


def row_lookup_from_payload(payload: dict[str, RadarCardData]) -> dict[str, RadarRow]:
    """vt_symbol → 行（优先保留 leader_score / leader_tier 更完整的行）。"""
    lookup: dict[str, RadarRow] = {}
    for data in payload.values():
        for row in data.rows:
            vt = str(row.vt_symbol or "").strip()
            if not vt:
                continue
            existing = lookup.get(vt)
            if existing is None:
                lookup[vt] = row
                continue
            if (row.leader_score or 0) > (existing.leader_score or 0):
                lookup[vt] = row
            elif row.leader_tier and not existing.leader_tier:
                lookup[vt] = row
    return lookup


def _build_limit_ladder_summary(data: RadarCardData | None) -> RadarLimitLadderSummary:
    if data is None or not data.rows:
        return RadarLimitLadderSummary()
    max_boards = 0.0
    top: list[str] = []
    for row in data.rows:
        boards = float(row.limit_times or 0)
        if boards > max_boards:
            max_boards = boards
        if len(top) < 5:
            top.append(row.vt_symbol)
    return RadarLimitLadderSummary(
        total=len(data.rows),
        max_limit_times=max_boards,
        top_vt_symbols=tuple(top),
    )


def build_radar_board_snapshot(payload: dict[str, RadarCardData]) -> RadarBoardSnapshot:
    """由雷达页 payload 构建全页快照。"""
    cycle = load_emotion_cycle_snapshot(fetch_if_missing=False)
    raw_entries = build_radar_resonance_list(payload)
    entries = enrich_resonance_entries(raw_entries, payload)
    leader_data = payload.get("leader_pick")
    leader_rows = leader_data.rows if leader_data is not None else ()
    dragon_1_count = sum(1 for row in leader_rows if row.leader_tier == "dragon_1")
    card_times = tuple(sorted((card_id, str(data.updated_at or "")) for card_id, data in payload.items() if data.updated_at))
    return RadarBoardSnapshot(
        board_updated_at=format_china_datetime(),
        emotion_stage=cycle.stage if cycle is not None else "",
        emotion_stage_label=cycle.stage_label if cycle is not None else "",
        allow_new_positions=cycle.allow_new_positions if cycle is not None else True,
        resonance_entries=entries,
        leader_pick_rows=leader_rows,
        limit_ladder_summary=_build_limit_ladder_summary(payload.get("discovery_limit_ladder")),
        card_updated_at=card_times,
        resonance_count=len(entries),
        dragon_1_count=dragon_1_count,
    )


def resonance_entry_to_row_dict(entry: RadarResonanceEntry, lookup: dict[str, RadarRow]) -> dict[str, Any]:
    """共振项 + payload 行合并为 dict（供主池过滤）。"""
    row = lookup.get(entry.vt_symbol)
    payload: dict[str, Any] = {
        "vt_symbol": entry.vt_symbol,
        "symbol": entry.symbol,
        "name": entry.name,
        "change_pct": entry.change_pct,
        "leader_tier": entry.leader_tier,
        "leader_score": entry.leader_score,
        "limit_times": entry.limit_times,
        "source": "radar_resonance",
    }
    if row is not None:
        for key in ("leader_tier", "leader_score", "limit_times", "change_pct"):
            value = getattr(row, key, None)
            if value not in (None, "", 0, 0.0):
                payload[key] = value
    return payload
