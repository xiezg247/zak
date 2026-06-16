"""板块成分龙头后台加载。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.sector_flow import SectorFlowRow
from vnpy_ashare.services.sector_flow_service import SectorFlowService


class SectorLeadersLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object, object, object)

    def __init__(
        self,
        service: SectorFlowService,
        sector: SectorFlowRow,
        *,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._sector = sector

    def run(self) -> None:
        try:
            leaders = self._service.load_sector_leaders(self._sector)
            history = self._service.load_sector_history(self._sector)
        except Exception as ex:
            self.finished.emit(self._sector, ex, ())
            return
        self.finished.emit(self._sector, leaders, history)
