"""指数卡片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.symbols import parse_tickflow_symbol
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import quote_change_color


class IndexCardWidget(QtWidgets.QFrame):
    """单张指数卡片（双击打开分析）。"""

    activated = QtCore.Signal(str)

    def __init__(
        self,
        label: str,
        quote: QuoteSnapshot,
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._quote = quote
        self._tf_symbol = quote.symbol
        self.setObjectName("IndexCard")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip("双击查看指数详情")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._name_label = QtWidgets.QLabel(label)
        self._name_label.setObjectName("IndexCardName")
        layout.addWidget(self._name_label)

        self._price_label = QtWidgets.QLabel("")
        self._price_label.setObjectName("IndexCardPrice")
        layout.addWidget(self._price_label)

        self._pct_label = QtWidgets.QLabel("")
        self._pct_label.setObjectName("IndexCardPct")
        layout.addWidget(self._pct_label)

        self._apply_colors()
        self._render_quote(quote)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            item = parse_tickflow_symbol(self._tf_symbol, self._label)
            if item is not None:
                self.activated.emit(item.vt_symbol)
        super().mouseDoubleClickEvent(event)

    def _apply_colors(self) -> None:
        tokens = theme_manager().tokens()
        color = quote_change_color(self._quote, tokens)
        self._price_label.setStyleSheet(f"color: {color};")
        self._pct_label.setStyleSheet(f"color: {color};")

    def _render_quote(self, quote: QuoteSnapshot) -> None:
        self._quote = quote
        self._price_label.setText(f"{quote.last_price:.2f}")
        self._pct_label.setText(f"{quote.change_pct:+.2f}%")

    def update_quote(self, label: str, quote: QuoteSnapshot) -> None:
        self._label = label
        self._tf_symbol = quote.symbol
        self._name_label.setText(label)
        self._render_quote(quote)
        self._apply_colors()
