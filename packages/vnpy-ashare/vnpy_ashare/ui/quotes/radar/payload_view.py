"""雷达 payload → UI 视图模型（纯函数，无 Qt）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from vnpy_ashare.domain.radar.snapshot import RadarBoardSnapshot
from vnpy_ashare.quotes.radar.loaders import (
    RadarCardData,
    build_radar_resonance_list,
    collect_radar_risk_vt_symbols,
    compute_radar_resonance,
)
from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar.radar_snapshot import (
    build_radar_board_snapshot,
    enrich_resonance_entries,
    row_lookup_from_payload,
)


@dataclass(frozen=True)
class ResonancePanelModel:
    snapshot: RadarBoardSnapshot
    statistical: tuple
    predictive: tuple
    row_lookup: dict
    risk_vt_symbols: frozenset[str]


def radar_row_hint_from_payload(
    payload: Mapping[str, RadarCardData],
    vt_symbol: str,
) -> dict[str, object] | None:
    """从已加载卡片行提取个股分析 hint。"""
    target = str(vt_symbol or "").strip()
    if not target:
        return None
    for data in payload.values():
        for row in data.rows:
            if row.vt_symbol != target:
                continue
            hint: dict[str, object] = {
                "vt_symbol": row.vt_symbol,
                "symbol": row.symbol,
                "name": row.name,
            }
            if row.price is not None:
                hint["last_price"] = row.price
            if row.change_pct is not None:
                hint["change_pct"] = row.change_pct
            return hint
    return None


def failed_card_placeholder(card_id: str, message: str) -> RadarCardData:
    spec = RADAR_CARD_BY_ID.get(card_id)
    return RadarCardData(
        card_id=card_id,
        title=spec.title if spec is not None else card_id,
        subtitle="",
        rows=(),
        empty_message=f"加载失败：{message}",
        updated_at="",
    )


def format_radar_status_text(
    *,
    active_workers: int,
    payload: Mapping[str, RadarCardData],
    resonance: dict[str, int] | None = None,
) -> str:
    if active_workers:
        return f"雷达加载中…（{active_workers} 张卡）"
    counts = resonance if resonance is not None else compute_radar_resonance(dict(payload))
    status = "就绪"
    if counts:
        status += f" · 共振 {len(counts)} 只"
    return status


def build_resonance_panel_model(payload: Mapping[str, RadarCardData]) -> ResonancePanelModel:
    data = dict(payload)
    snapshot = build_radar_board_snapshot(data)
    return ResonancePanelModel(
        snapshot=snapshot,
        statistical=enrich_resonance_entries(
            build_radar_resonance_list(data, mode="statistical"),
            data,
        ),
        predictive=enrich_resonance_entries(
            build_radar_resonance_list(data, mode="predictive"),
            data,
        ),
        row_lookup=row_lookup_from_payload(data),
        risk_vt_symbols=collect_radar_risk_vt_symbols(data),
    )
