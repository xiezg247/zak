"""日 K / 分 K 策略参考线说明。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.trading.signals.mode_reference import ModeReferenceLine
from vnpy_ashare.ui.quotes.chart.daily import (
    REF_BUY_LINE_COLOR,
    REF_LAST_PRICE_LINE_COLOR,
    REF_SELL_LINE_COLOR,
)
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.tokens import ThemeTokens

_REFERENCE_LINE_SPECS: tuple[tuple[str, str, str], ...] = (
    (REF_BUY_LINE_COLOR, "ref_buy", "支撑锚点"),
    (REF_SELL_LINE_COLOR, "ref_sell", "阻力锚点"),
    (REF_LAST_PRICE_LINE_COLOR, "last_price", "现价"),
)


class ReferenceLineLegendBar(QtWidgets.QWidget):
    """K 线叠加虚线说明（日 K 锚点 / 分 K 模式线）。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReferenceLineLegendBar")
        self._entries: dict[str, tuple[QtWidgets.QLabel, str, str]] = {}
        self._values: dict[str, float | None] = {
            "ref_buy": None,
            "ref_sell": None,
            "last_price": None,
        }
        self._mode_labels: list[QtWidgets.QLabel] = []
        self._mode_values: list[tuple[str, str, float]] = []

        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(8, 3, 8, 3)
        self._layout.setSpacing(14)

        for color, key, label in _REFERENCE_LINE_SPECS:
            item = QtWidgets.QLabel()
            item.setTextFormat(QtCore.Qt.TextFormat.RichText)
            self._entries[key] = (item, color, label)
            self._layout.addWidget(item)

        self._layout.addStretch()
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
        self._clear_mode_labels()
        for key, (label, _color, _text) in self._entries.items():
            label.setVisible(key in {"ref_buy", "ref_sell", "last_price"})
        self._values = {
            "ref_buy": ref_buy if ref_buy is not None and ref_buy > 0 else None,
            "ref_sell": ref_sell if ref_sell is not None and ref_sell > 0 else None,
            "last_price": last_price if last_price is not None and last_price > 0 else None,
        }
        self._refresh_entries()

    def set_mode_reference_lines(
        self,
        lines: tuple[ModeReferenceLine, ...],
        *,
        last_price: float | None = None,
        hint: str = "",
    ) -> None:
        for _key, (label, _color, _text) in self._entries.items():
            label.setVisible(False)
        self._clear_mode_labels()
        self._mode_values = [(line.color, line.label, line.price) for line in lines if line.price > 0]
        if last_price is not None and last_price > 0:
            self._mode_values.append((REF_LAST_PRICE_LINE_COLOR, "现价", last_price))
        for _color, _label, _price in self._mode_values:
            item = QtWidgets.QLabel()
            item.setTextFormat(QtCore.Qt.TextFormat.RichText)
            item.setToolTip(hint)
            self._mode_labels.append(item)
            insert_at = max(0, self._layout.count() - 1)
            self._layout.insertWidget(insert_at, item)
        self._refresh_entries()

    def clear(self) -> None:
        self.set_reference_lines()

    def has_entries(self) -> bool:
        return any(self._values.values()) or bool(self._mode_values)

    def _clear_mode_labels(self) -> None:
        for label in self._mode_labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self._mode_labels.clear()
        self._mode_values.clear()

    def _refresh_entries(self) -> None:
        tokens = theme_manager().tokens()
        for key, (label, color, text) in self._entries.items():
            if not label.isVisible():
                continue
            value = self._values.get(key)
            if value is None:
                label.clear()
                label.setVisible(False)
                continue
            label.setVisible(True)
            label.setText(self._legend_text(tokens, color, text, value))
        for (color, text, value), label in zip(self._mode_values, self._mode_labels, strict=False):
            label.setVisible(True)
            label.setText(self._legend_text(tokens, color, text, value))

    @staticmethod
    def _legend_text(tokens: ThemeTokens, color: str, text: str, value: float) -> str:
        return (
            f'<span style="color:{color}; font-weight:600;">╌╌</span>'
            f'<span style="color:{tokens.text_primary};"> {text}</span>'
            f'<span style="color:{tokens.text_muted};"> {value:.2f}</span>'
        )

    def _apply_theme(self, tokens: ThemeTokens) -> None:
        self._refresh_entries()
