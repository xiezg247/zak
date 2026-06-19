"""板块近 N 日轮动后台加载。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market.sector_flow import SectorFlowSnapshot
from vnpy_ashare.services.sector_flow import SectorFlowService


class SectorFlowRotationLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        service: SectorFlowService,
        *,
        snapshot: SectorFlowSnapshot | None = None,
        sector_kind: str = "industry",
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._snapshot = snapshot
        self._sector_kind = sector_kind
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            rotation = self._service.load_rotation_snapshot(self._snapshot, sector_kind=self._sector_kind)
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        if self._cancelled:
            return
        self.finished.emit(rotation)
