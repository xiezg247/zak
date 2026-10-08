"""雷达全页快照（供 AI / vnpy-radar 读取）。"""

from __future__ import annotations

from vnpy_ashare.domain.radar.snapshot import RadarBoardSnapshot

_snapshot: RadarBoardSnapshot | None = None


def set_radar_board_snapshot(snapshot: RadarBoardSnapshot) -> None:
    global _snapshot
    _snapshot = snapshot


def get_radar_board_snapshot() -> RadarBoardSnapshot | None:
    return _snapshot


def clear_radar_board_snapshot() -> None:
    global _snapshot
    _snapshot = None
