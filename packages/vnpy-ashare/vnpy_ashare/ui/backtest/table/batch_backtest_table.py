"""批量回测对比表格（可复用）。"""

from __future__ import annotations

from typing import Any, Protocol

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.backtest.run_store import BacktestRunRecord
from vnpy_ashare.screener.batch.batch_actions import BatchBacktestRow
from vnpy_common.ui.scroll_area import style_market_table_scroll_bars
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_BATCH_COMPARE_ROW_HEIGHT = 30
_SORT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 2
_METRIC_COLS = {3: "total_return", 4: "max_drawdown", 5: "sharpe_ratio", 6: "total_trade_count"}


class BatchCompareTableDelegate(QtWidgets.QStyledItemDelegate):
    """回测对比表：强制垂直居中，避免 QSS padding 导致内容贴顶。"""

    def initStyleOption(
        self,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        super().initStyleOption(option, index)
        horizontal = option.displayAlignment & QtCore.Qt.AlignmentFlag.AlignHorizontal_Mask
        option.displayAlignment = horizontal | QtCore.Qt.AlignmentFlag.AlignVCenter


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

    HEADERS = ["#", "代码", "名称", "总收益", "最大回撤", "夏普", "交易次数", "状态"]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self.setObjectName("BatchCompareTable")
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(_BATCH_COMPARE_ROW_HEIGHT)
        self.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.setItemDelegate(BatchCompareTableDelegate(self))
        style_market_table_scroll_bars(self)
        header = self.horizontalHeader()
        if hasattr(header, "setStretchHighlightSections"):
            header.setStretchHighlightSections(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 40)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 3, 4, 5, 6):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

    def load_rows(self, rows: list[Any]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        tokens = theme_manager().tokens()
        muted = QtGui.QColor(tokens.text_muted)
        success = QtGui.QColor(tokens.semantic_success)
        danger = QtGui.QColor(tokens.danger_btn_text)
        for row_index, row in enumerate(rows):
            error_text = str(getattr(row, "error", "") or "").strip()
            rank_item = QtWidgets.QTableWidgetItem(str(row_index + 1))
            rank_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            rank_item.setForeground(muted)
            rank_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            rank_item.setData(_SORT_ROLE, row_index + 1)
            self.setItem(row_index, 0, rank_item)

            symbol_item = QtWidgets.QTableWidgetItem(getattr(row, "vt_symbol", ""))
            symbol_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.setItem(row_index, 1, symbol_item)

            name_text = getattr(row, "name", "") or "—"
            name_item = QtWidgets.QTableWidgetItem(name_text)
            name_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)
            if name_text not in ("", "—"):
                name_item.setToolTip(name_text)
            self.setItem(row_index, 2, name_item)

            for col_index, text, metric_key in (
                (3, self._fmt_return(getattr(row, "total_return", None)), "total_return"),
                (4, self._fmt_drawdown(getattr(row, "max_drawdown", None)), "max_drawdown"),
                (5, self._fmt_metric(getattr(row, "sharpe_ratio", None)), "sharpe_ratio"),
                (6, self._trade_count_text(row), "total_trade_count"),
            ):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight)
                metric = getattr(row, metric_key, None)
                if metric is not None:
                    sort_value = self._metric_value(row, col_index)
                    if sort_value is not None:
                        item.setData(_SORT_ROLE, sort_value)
                if col_index == 3 and isinstance(metric, (int, float)):
                    item.setForeground(QtGui.QColor(pct_change_color(float(metric), tokens)))
                elif col_index == 4 and isinstance(metric, (int, float)):
                    item.setForeground(danger if float(metric) != 0 else muted)
                self.setItem(row_index, col_index, item)

            status_text = error_text or "成功"
            status_item = QtWidgets.QTableWidgetItem(status_text)
            status_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if error_text:
                status_item.setForeground(danger)
                status_item.setToolTip(error_text)
            else:
                status_item.setForeground(success)
            self.setItem(row_index, 7, status_item)

        self.clearSelection()
        self.setCurrentItem(None)
        self.setSortingEnabled(True)

    @staticmethod
    def _metric_value(row: Any, col_index: int) -> float | None:
        key = _METRIC_COLS.get(col_index)
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
    def _fmt_metric(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value:.2f}"

    @staticmethod
    def _fmt_return(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value:+.2f}%"

    @staticmethod
    def _fmt_drawdown(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{abs(value):.2f}%"
