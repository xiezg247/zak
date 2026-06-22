"""雷达 Service Facade（快照读取）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.radar.snapshot import RadarBoardSnapshot
from vnpy_ashare.quotes.radar.radar_board_store import get_radar_board_snapshot
from vnpy_ashare.services.base import BaseService
from vnpy_common.domain.serialize import dump_python


class RadarService(BaseService):
    """雷达盘面快照（只读）。"""

    def get_board_snapshot(self) -> RadarBoardSnapshot | None:
        return get_radar_board_snapshot()

    def snapshot_to_dict(self, snapshot: RadarBoardSnapshot | None = None) -> dict[str, Any]:
        data = snapshot if snapshot is not None else get_radar_board_snapshot()
        if data is None:
            return {"status": "empty", "message": "雷达快照为空，请先在雷达页刷新"}
        return {"status": "ok", **dump_python(data)}
