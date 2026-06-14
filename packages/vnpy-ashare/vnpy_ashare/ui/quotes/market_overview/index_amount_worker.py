"""指数成交额历史后台加载。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.index_amount import IndexAmountSeries
from vnpy_ashare.integrations.tushare.index_amount import DEFAULT_TRADING_DAYS, fetch_index_amount_history


class IndexAmountLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        ts_code: str,
        *,
        label: str,
        trading_days: int = DEFAULT_TRADING_DAYS,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ts_code = ts_code
        self._label = label
        self._trading_days = trading_days

    def run(self) -> None:
        try:
            series = fetch_index_amount_history(
                self._ts_code,
                label=self._label,
                trading_days=self._trading_days,
            )
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        self.finished.emit(series)
