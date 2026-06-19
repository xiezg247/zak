"""板块资金监控页。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.sector_flow.controller import SectorFlowController
from vnpy_ashare.ui.sector_flow.panel import SectorFlowPanel
from vnpy_common.ui.feedback import PageToastHost


class SectorFlowPageWidget(QtWidgets.QWidget):
    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")

        self.panel = SectorFlowPanel(self)
        self._status = QtWidgets.QLabel("就绪")
        self._status.setObjectName("BottomBarMeta")

        bottom = QtWidgets.QHBoxLayout()
        bottom.setContentsMargins(8, 2, 8, 4)
        bottom.addWidget(self._status, stretch=1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.panel, stretch=1)
        layout.addLayout(bottom)
        self._toast = PageToastHost(self)
        layout.addWidget(self._toast)

        self._controller = SectorFlowController(self, main_engine, event_engine)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def activate(self) -> None:
        self._controller.activate()

    def deactivate(self) -> None:
        self._controller.deactivate()

    def focus_sectors(
        self,
        sector_ids: list[str],
        *,
        tab: str = "default",
        sector_kind: str | None = None,
    ) -> None:
        self._controller.focus_sectors(sector_ids, tab=tab, sector_kind=sector_kind)

    def closeEvent(self, event) -> None:
        self.deactivate()
        super().closeEvent(event)
