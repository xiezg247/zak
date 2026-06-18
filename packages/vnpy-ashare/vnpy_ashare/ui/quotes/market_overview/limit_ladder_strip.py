"""市场页连板梯队条。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.quotes.radar.radar_limit_ladder import LADDER_BUCKET_LABELS
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class LimitLadderStrip(QtWidgets.QWidget):
    """紧凑展示连板梯队家数。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketLimitLadderStrip")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 4)
        layout.setSpacing(6)

        title = QtWidgets.QLabel("连板梯队")
        title.setObjectName("MarketLimitLadderTitle")
        layout.addWidget(title)

        self._chips: dict[str, _LadderChip] = {}
        for label in LADDER_BUCKET_LABELS:
            chip = _LadderChip(label, parent=self)
            self._chips[label] = chip
            layout.addWidget(chip)
        layout.addStretch(1)

        self._empty_label = QtWidgets.QLabel("暂无涨停池数据")
        self._empty_label.setObjectName("MarketLimitLadderEmpty")
        layout.addWidget(self._empty_label)
        self._empty_label.hide()

        theme_manager().register_callback(lambda _tokens: self._refresh_theme())

    def apply_counts(self, counts: dict[str, int] | None) -> None:
        data = counts or {}
        total = sum(int(data.get(label, 0)) for label in LADDER_BUCKET_LABELS)
        if total <= 0:
            for chip in self._chips.values():
                chip.hide()
            self._empty_label.show()
            return
        self._empty_label.hide()
        for label, chip in self._chips.items():
            chip.set_count(int(data.get(label, 0)))
            chip.show()

    def _refresh_theme(self) -> None:
        for chip in self._chips.values():
            chip.refresh_theme()


class _LadderChip(QtWidgets.QFrame):
    def __init__(self, bucket: str, *, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketLimitLadderChip")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)
        self._label = QtWidgets.QLabel(bucket)
        self._label.setObjectName("MarketLimitLadderChipLabel")
        self._value = QtWidgets.QLabel("0")
        self._value.setObjectName("MarketLimitLadderChipValue")
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_count(self, count: int) -> None:
        self._value.setText(str(count))
        self.refresh_theme()

    def refresh_theme(self) -> None:
        tokens = theme_manager().tokens()
        color = pct_change_color(1.0, tokens) if self._value.text() not in {"0", "—"} else tokens.text_muted
        self._value.setStyleSheet(f"color: {color};")
