"""雷达快照 store 测试。"""

from __future__ import annotations

from vnpy_ashare.domain.radar.card import RadarCardData, RadarRow
from vnpy_ashare.domain.radar.snapshot import RadarBoardSnapshot
from vnpy_ashare.quotes.radar.radar_board_store import (
    clear_radar_board_snapshot,
    get_radar_board_snapshot,
    set_radar_board_snapshot,
)
from vnpy_ashare.quotes.radar.radar_snapshot import build_radar_board_snapshot


def _sample_row(vt: str, *, tier: str = "", score: float | None = None) -> RadarRow:
    return RadarRow(
        vt_symbol=vt,
        name=vt.split(".")[0],
        symbol=vt.split(".")[0],
        price=10.0,
        change_pct=9.5,
        metric_label="",
        metric_value="",
        sub_label="",
        sub_value="",
        leader_tier=tier,
        leader_score=score,
        limit_times=2.0 if tier else None,
    )


def test_build_and_store_snapshot() -> None:
    clear_radar_board_snapshot()
    payload = {
        "leader_pick": RadarCardData(
            card_id="leader_pick",
            title="选股·龙头",
            subtitle="",
            rows=(_sample_row("600000.SSE", tier="dragon_1", score=88.0),),
            empty_message="",
            updated_at="2026-06-22 10:00:00",
        ),
        "discovery_volume_surge": RadarCardData(
            card_id="discovery_volume_surge",
            title="发现·放量",
            subtitle="",
            rows=(_sample_row("600000.SSE"),),
            empty_message="",
            updated_at="2026-06-22 10:00:00",
        ),
    }
    snapshot = build_radar_board_snapshot(payload)
    assert snapshot.dragon_1_count == 1
    assert snapshot.resonance_count >= 1
    set_radar_board_snapshot(snapshot)
    stored = get_radar_board_snapshot()
    assert stored is not None
    assert stored.dragon_1_count == 1
    clear_radar_board_snapshot()


def test_empty_snapshot_roundtrip() -> None:
    snap = RadarBoardSnapshot(board_updated_at="t")
    set_radar_board_snapshot(snap)
    assert get_radar_board_snapshot() == snap
    clear_radar_board_snapshot()
