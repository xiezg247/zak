"""批量回测对比表格（可复用）。"""

from __future__ import annotations

from typing import Any, Protocol

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.backtest.run_store import BacktestRunRecord
from vnpy_ashare.screener.batch.batch_actions import BatchBacktestRow
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class _RowLike(Protocol):
    vt_symbol: str
    name: str
    total_return: float | None
    max_drawdown: float | None
    sharpe_ratio: float | None
    total_trade_count: int | None
    error: str


def record_to_row(record: BacktestRunRecord) -> BatchBacktestRow:
    stats = record.raw_statistics or {}
    return BatchBacktestRow(
        vt_symbol=record.vt_symbol,
        name=str(stats.get("name", "") or ""),
        total_return=record.total_return,
        max_drawdown=record.max_drawdown,
        sharpe_ratio=record.sharpe_ratio,
        total_trade_count=record.trade_count,
        error=str(stats.get("error", "") or ""),
    )


class BatchBacktestTableWidget(QtWidgets.QTableWidget):
    """批量回测结果大表格。"""

    HEADERS = ["代码", "名称", "总收益", "最大回撤", "夏普", "交易次数", "状态"]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self.setObjectName("MarketTable")
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        if hasattr(header, "setStretchHighlightSections"):
            header.setStretchHighlightSections(False)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (0, 2, 3, 4, 5):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

    def load_rows(self, rows: list[Any]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                getattr(row, "vt_symbol", ""),
                getattr(row, "name", ""),
                self._fmt(getattr(row, "total_return", None)),
                self._fmt(getattr(row, "max_drawdown", None)),
                self._fmt(getattr(row, "sharpe_ratio", None)),
                self._trade_count_text(row),
                getattr(row, "error", "") or "—",
            ]
            error_text = str(getattr(row, "error", "") or "").strip()
            tokens = theme_manager().tokens()
            for col_index, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_index == 1:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)
                else:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                if col_index == 2:
                    metric = getattr(row, "total_return", None)
                    if isinstance(metric, (int, float)):
                        color = pct_change_color(float(metric), tokens)
                        item.setForeground(QtGui.QColor(color))
                if col_index == 6 and error_text:
                    item.setForeground(QtGui.QColor(tokens.danger_btn_text))
                if col_index in (2, 3, 4, 5):
                    metric = self._metric_value(row, col_index)
                    if metric is not None:
                        item.setData(QtCore.Qt.ItemDataRole.UserRole, metric)
                self.setItem(row_index, col_index, item)
        self.setSortingEnabled(True)

    @staticmethod
    def _metric_value(row: Any, col_index: int) -> float | None:
        mapping = {2: "total_return", 3: "max_drawdown", 4: "sharpe_ratio", 5: "total_trade_count"}
        key = mapping.get(col_index)
        if not key:
            return None
        value = getattr(row, key, None)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _trade_count_text(row: Any) -> str:
        value = getattr(row, "total_trade_count", None)
        return str(value) if value is not None else "—"

    @staticmethod
    def _fmt(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value:.2f}"
