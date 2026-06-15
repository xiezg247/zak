"""市场页今日异动 compact 横条。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData, RadarRow
from vnpy_common.ui.theme import theme_manager

DISPLAY_TOP_N = 5


def _chip_tone(change_pct: float | None) -> str:
    if change_pct is None:
        return "flat"
    if change_pct > 0:
        return "rise"
    if change_pct < 0:
        return "fall"
    return "flat"


def _apply_chip_tone(widget: QtWidgets.QWidget, change_pct: float | None) -> None:
    widget.setProperty("chipTone", _chip_tone(change_pct))
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


class _DiscoveryChip(QtWidgets.QPushButton):
    """单行异动 chip：名称 + 涨幅。"""

    activated = QtCore.Signal(str)

    def __init__(self, row: RadarRow, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._vt_symbol = row.vt_symbol
        self._change_pct = row.change_pct
        self.setObjectName("MarketDiscoveryChip")
        self.setFlat(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        change = f"{row.change_pct:+.2f}%" if row.change_pct is not None else "—"
        self.setText(f"{row.name}  {change}")
        self.setToolTip(f"{row.name} ({row.symbol}) · {row.metric_label} {row.metric_value}")
        self.clicked.connect(lambda: self.activated.emit(self._vt_symbol))
        _apply_chip_tone(self, row.change_pct)

    def refresh_theme(self) -> None:
        _apply_chip_tone(self, self._change_pct)


class MarketDiscoveryStrip(QtWidgets.QWidget):
    """放量 / 资金异动 Top N，点击定位主表。"""

    row_activated = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketDiscoveryStrip")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(12, 6, 12, 2)
        title = QtWidgets.QLabel("今日异动")
        title.setObjectName("MarketDiscoverySectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        root.addLayout(title_row)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(12, 0, 12, 10)
        body.setSpacing(0)

        self._volume_group = self._build_group("放量")
        divider = QtWidgets.QFrame(self)
        divider.setObjectName("MarketDiscoveryDivider")
        divider.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        divider.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        divider.setFixedWidth(1)
        self._moneyflow_group = self._build_group("资金")

        body.addWidget(self._volume_group, stretch=1)
        body.addWidget(divider)
        body.addWidget(self._moneyflow_group, stretch=1)
        root.addLayout(body)

        self._loading = False
        theme_manager().register_callback(lambda _tokens: self._refresh_chip_colors())

    def _build_group(self, title: str) -> QtWidgets.QWidget:
        host = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(host)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        label = QtWidgets.QLabel(title)
        label.setObjectName("MarketDiscoveryTitle")
        layout.addWidget(label)

        scroll = QtWidgets.QScrollArea(host)
        scroll.setObjectName("MarketDiscoveryScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(30)

        chip_host = QtWidgets.QWidget()
        chip_host.setObjectName("MarketDiscoveryChipHost")
        chip_layout = QtWidgets.QHBoxLayout(chip_host)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.setSpacing(6)
        chip_layout.addStretch(1)
        scroll.setWidget(chip_host)
        layout.addWidget(scroll, stretch=1)

        empty = QtWidgets.QLabel("—")
        empty.setObjectName("MarketDiscoveryEmpty")
        layout.addWidget(empty)

        host._scroll = scroll
        host._chip_host = chip_host
        host._chip_layout = chip_layout
        host._empty = empty
        return host

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            for group in (self._volume_group, self._moneyflow_group):
                group._empty.setText("加载中…")
                group._empty.show()
                group._scroll.hide()

    def apply_cards(self, volume: RadarCardData | None, moneyflow: RadarCardData | None) -> None:
        self._loading = False
        self._apply_group(self._volume_group, volume)
        self._apply_group(self._moneyflow_group, moneyflow)

    def _apply_group(self, group: QtWidgets.QWidget, data: RadarCardData | None) -> None:
        chip_layout: QtWidgets.QHBoxLayout = group._chip_layout
        empty: QtWidgets.QLabel = group._empty

        while chip_layout.count() > 1:
            item = chip_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        rows = tuple(data.rows[:DISPLAY_TOP_N]) if data is not None else ()
        if not rows:
            message = data.empty_message if data is not None and data.empty_message else "—"
            empty.setText(message if not self._loading else "加载中…")
            empty.show()
            group._scroll.hide()
            return

        empty.hide()
        group._scroll.show()
        for index, row in enumerate(rows):
            chip = _DiscoveryChip(row, parent=group._chip_host)
            chip.activated.connect(self.row_activated.emit)
            chip_layout.insertWidget(index, chip)

    def _refresh_chip_colors(self) -> None:
        for group in (self._volume_group, self._moneyflow_group):
            chip_host: QtWidgets.QWidget = group._chip_host
            for chip in chip_host.findChildren(_DiscoveryChip):
                chip.refresh_theme()
