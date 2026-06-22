"""单板块策略扫描后台任务。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market.sector_flow import SectorFlowOutlookRow, SectorFlowRow
from vnpy_ashare.services.sector_flow_outlook_strategy import build_sector_strategy_outlook_row


class SectorFlowSectorStrategyWorker(QtCore.QThread):
    """单板块策略扫描线程（勿用 finished 命名，避免与 QThread.finished 冲突）。"""

    scan_finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        sector: SectorFlowRow,
        *,
        strategy_class: str,
        forward_dates: tuple[str, ...] = (),
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sector = sector
        self._strategy_class = str(strategy_class or "").strip()
        self._forward_dates = tuple(forward_dates)
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            self.failed.emit("")
            return
        if not self._strategy_class:
            self.failed.emit("未选择策略")
            return
        try:
            row = build_sector_strategy_outlook_row(
                self._sector,
                strategy_class=self._strategy_class,
                forward_dates=self._forward_dates or None,
            )
        except Exception as ex:
            if not self._cancelled:
                self.failed.emit(str(ex))
            else:
                self.failed.emit("")
            return
        if self._cancelled:
            self.failed.emit("")
            return
        if not isinstance(row, SectorFlowOutlookRow):
            self.failed.emit("策略扫描结果无效")
            return
        self.scan_finished.emit(row)


__all__ = ["SectorFlowSectorStrategyWorker"]
