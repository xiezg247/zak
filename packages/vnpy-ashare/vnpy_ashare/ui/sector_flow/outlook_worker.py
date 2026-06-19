"""板块未来 N 日展望后台加载。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market.sector_flow import SectorFlowSnapshot
from vnpy_ashare.services.sector_flow import SectorFlowService
from vnpy_ashare.services.sector_flow_outlook_strategy import (
    scan_strategy_outlook_cache,
    strategy_outlook_cache_ready,
)


class SectorFlowOutlookLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        service: SectorFlowService,
        *,
        snapshot: SectorFlowSnapshot | None = None,
        sector_kind: str = "industry",
        strategy_class: str | None = None,
        scan_strategy: bool = False,
        scan_if_missing: bool = False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._snapshot = snapshot
        self._sector_kind = sector_kind
        self._strategy_class = strategy_class
        self._scan_strategy = scan_strategy
        self._scan_if_missing = scan_if_missing
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        strategy_class = str(self._strategy_class or "").strip()
        try:
            if strategy_class and (self._scan_strategy or (self._scan_if_missing and not strategy_outlook_cache_ready(strategy_class))):
                scan_strategy_outlook_cache(strategy_class)
        except Exception as ex:
            self.failed.emit(f"策略扫描失败：{ex}")
            return
        if self._cancelled:
            return
        try:
            bundle = self._service.load_outlook_bundle(
                self._snapshot,
                sector_kind=self._sector_kind,
                strategy_class=strategy_class or None,
            )
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        if self._cancelled:
            return
        self.finished.emit(bundle)
