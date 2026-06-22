"""雷达全页快照（供 AI / vnpy-radar 读取）。"""

from __future__ import annotations

from vnpy_ashare.domain.radar.snapshot import RadarBoardSnapshot
from vnpy_ashare.domain.time.china import format_china_datetime

_snapshot: RadarBoardSnapshot | None = None


def set_radar_board_snapshot(snapshot: RadarBoardSnapshot) -> None:
    global _snapshot
    _snapshot = snapshot


def get_radar_board_snapshot() -> RadarBoardSnapshot | None:
    return _snapshot


def radar_board_updated_at() -> str | None:
    if _snapshot is None or not _snapshot.board_updated_at:
        return None
    return _snapshot.board_updated_at


def clear_radar_board_snapshot() -> None:
    global _snapshot
    _snapshot = None


def empty_radar_board_snapshot() -> RadarBoardSnapshot:
    return RadarBoardSnapshot(board_updated_at=format_china_datetime())
