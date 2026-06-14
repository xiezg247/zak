"""选股结果行业分布可视化组件。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution


class SectorDistributionPanel(QtWidgets.QWidget):
    """结果区行业分布：条形占比 + 涨幅着色。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorDistributionPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(4)

        self._title = QtWidgets.QLabel("行业分布")
        self._title.setObjectName("ScreenerSubheading")
        layout.addWidget(self._title)

        self._bars_host = QtWidgets.QWidget()
        self._bars_layout = QtWidgets.QVBoxLayout(self._bars_host)
        self._bars_layout.setContentsMargins(0, 0, 0, 0)
        self._bars_layout.setSpacing(3)
        layout.addWidget(self._bars_host)

        self.hide()

    def apply_rows(self, rows: list[dict[str, Any]], *, top_n: int = 6) -> None:
        stats = compute_sector_distribution(
            attach_industry(rows),
            top_n=top_n,
            min_stocks=1,
        )
        self._clear_bars()
        if not stats:
            self.hide()
            return

        max_count = max(int(item["count"]) for item in stats)
        for item in stats:
            self._bars_layout.addWidget(_SectorBarRow(item, max_count=max_count))
        self.show()

    def clear(self) -> None:
        self._clear_bars()
        self.hide()

    def _clear_bars(self) -> None:
        while self._bars_layout.count():
            child = self._bars_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()


class _SectorBarRow(QtWidgets.QWidget):
    def __init__(self, stat: dict[str, Any], *, max_count: int) -> None:
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        industry = str(stat.get("industry") or "—")
        count = int(stat.get("count") or 0)
        avg_change = float(stat.get("avg_change_pct") or 0)
        advance_pct = float(stat.get("advance_pct") or 0)

        name_label = QtWidgets.QLabel(industry[:10])
        name_label.setObjectName("SectorBarName")
        name_label.setFixedWidth(72)
        layout.addWidget(name_label)

        bar = QtWidgets.QProgressBar()
        bar.setObjectName("SectorBarProgress")
        bar.setTextVisible(False)
        bar.setRange(0, max(max_count, 1))
        bar.setValue(count)
        bar.setFixedHeight(10)
        layout.addWidget(bar, stretch=1)

        meta = QtWidgets.QLabel(f"{count}只 {avg_change:+.2f}% · 涨{advance_pct:.0f}%")
        meta.setObjectName("SectorBarMeta")
        if avg_change >= 2:
            meta.setProperty("tone", "up")
        elif avg_change <= -2:
            meta.setProperty("tone", "down")
        layout.addWidget(meta)
