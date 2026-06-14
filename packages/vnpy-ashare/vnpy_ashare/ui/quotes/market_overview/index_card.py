"""指数卡片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import quote_change_color

_SINGLE_CLICK_MS = 280


class IndexCardWidget(QtWidgets.QFrame):
    """单张指数卡片（单击查看近30日成交额）。"""

    amount_popup_requested = QtCore.Signal(str, str)

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
        self.setToolTip("单击查看近30日成交额")

        self._click_timer = QtCore.QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(_SINGLE_CLICK_MS)
        self._click_timer.timeout.connect(self._emit_amount_popup)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
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

    @property
    def tf_symbol(self) -> str:
        return self._tf_symbol

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._click_timer.start()
        super().mousePressEvent(event)

    def _emit_amount_popup(self) -> None:
        self.amount_popup_requested.emit(self._tf_symbol, self._label)

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
