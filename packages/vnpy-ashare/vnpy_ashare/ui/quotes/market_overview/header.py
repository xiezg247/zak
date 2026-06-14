"""市场页顶部统一外壳：概览 + 异动带。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.market_discovery.panel import MarketDiscoveryStrip
from vnpy_ashare.ui.quotes.market_overview.panel import MarketOverviewPanel


class MarketHeaderPanel(QtWidgets.QWidget):
    """概览带与异动带合并为单一头部区域。"""

    def __init__(
        self,
        overview: MarketOverviewPanel,
        discovery: MarketDiscoveryStrip,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MarketHeaderPanel")
        self.overview = overview
        self.discovery = discovery

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(overview)

        divider = QtWidgets.QFrame(self)
        divider.setObjectName("MarketHeaderDivider")
        divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        divider.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        divider.setFixedHeight(1)
        root.addWidget(divider)

        root.addWidget(discovery)
