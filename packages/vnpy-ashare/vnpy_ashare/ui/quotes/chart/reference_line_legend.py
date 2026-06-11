"""日 K 策略参考线说明。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.chart.daily import (
    REF_BUY_LINE_COLOR,
    REF_LAST_PRICE_LINE_COLOR,
    REF_SELL_LINE_COLOR,
)
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.tokens import ThemeTokens

_REFERENCE_LINE_SPECS: tuple[tuple[str, str, str], ...] = (
    (REF_BUY_LINE_COLOR, "ref_buy", "支撑锚点"),
    (REF_SELL_LINE_COLOR, "ref_sell", "阻力锚点"),
    (REF_LAST_PRICE_LINE_COLOR, "last_price", "现价"),
)


class ReferenceLineLegendBar(QtWidgets.QWidget):
    """日 K 叠加虚线：支撑锚点 / 阻力锚点 / 现价。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReferenceLineLegendBar")
        self._entries: dict[str, tuple[QtWidgets.QLabel, str, str]] = {}
        self._values: dict[str, float | None] = {
            "ref_buy": None,
            "ref_sell": None,
            "last_price": None,
        }

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(14)

        for color, key, label in _REFERENCE_LINE_SPECS:
            item = QtWidgets.QLabel()
            item.setTextFormat(QtCore.Qt.TextFormat.RichText)
            self._entries[key] = (item, color, label)
            layout.addWidget(item)

        layout.addStretch()
        self._apply_theme(theme_manager().tokens())
        theme_manager().register_callback(self._apply_theme)
        self.setVisible(False)

    def set_reference_lines(
        self,
        *,
        ref_buy: float | None = None,
        ref_sell: float | None = None,
        last_price: float | None = None,
    ) -> None:
        self._values = {
            "ref_buy": ref_buy if ref_buy is not None and ref_buy > 0 else None,
            "ref_sell": ref_sell if ref_sell is not None and ref_sell > 0 else None,
            "last_price": last_price if last_price is not None and last_price > 0 else None,
        }
        self._refresh_entries()

    def clear(self) -> None:
        self.set_reference_lines()

    def has_entries(self) -> bool:
        return any(self._values.values())

    def _refresh_entries(self) -> None:
        tokens = theme_manager().tokens()
        for key, (label, color, text) in self._entries.items():
            value = self._values.get(key)
            if value is None:
                label.clear()
                label.setVisible(False)
                continue
            label.setVisible(True)
            label.setText(
                f'<span style="color:{color}; font-weight:600;">╌╌</span>'
                f'<span style="color:{tokens.text_primary};"> {text}</span>'
                f'<span style="color:{tokens.text_muted};"> {value:.2f}</span>'
            )

    def _apply_theme(self, tokens: ThemeTokens) -> None:
        self._refresh_entries()
