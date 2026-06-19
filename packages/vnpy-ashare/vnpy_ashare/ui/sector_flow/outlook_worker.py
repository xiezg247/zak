"""板块未来 N 日展望后台加载。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market.sector_flow import SectorFlowSnapshot
from vnpy_ashare.services.sector_flow import SectorFlowService
from vnpy_ashare.services.sector_flow_outlook_strategy import scan_strategy_outlook_cache

_LOAD_CONTINUATION = "continuation"
_LOAD_STRATEGY = "strategy"


class SectorFlowOutlookLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(str)

    def __init__(
        self,
        service: SectorFlowService,
        *,
        snapshot: SectorFlowSnapshot | None = None,
        sector_kind: str = "industry",
        strategy_class: str | None = None,
        load_kind: str = _LOAD_CONTINUATION,
        scan_strategy: bool = False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._snapshot = snapshot
        self._sector_kind = sector_kind
        self._strategy_class = strategy_class
        self._load_kind = str(load_kind or _LOAD_CONTINUATION).strip() or _LOAD_CONTINUATION
        self._scan_strategy = scan_strategy
        self._cancelled = False
        self._scan_summary = ""

    @property
    def strategy_class(self) -> str:
        return str(self._strategy_class or "").strip()

    @property
    def scan_summary(self) -> str:
        return str(self._scan_summary or "").strip()

    def request_cancel(self) -> None:
        self._cancelled = True

    def _fail_if_cancelled(self) -> bool:
        if self._cancelled:
            self.failed.emit("")
            return True
        return False

    def run(self) -> None:
        if self._fail_if_cancelled():
            return
        strategy_class = self.strategy_class
        try:
            if self._load_kind == _LOAD_STRATEGY and strategy_class and self._scan_strategy:
                self._scan_summary = scan_strategy_outlook_cache(
                    strategy_class,
                    on_progress=self.progress.emit,
                )
        except Exception as ex:
            if not self._cancelled:
                self.failed.emit(f"策略扫描失败：{ex}")
            else:
                self.failed.emit("")
            return
        if self._fail_if_cancelled():
            return
        try:
            if self._load_kind == _LOAD_STRATEGY:
                bundle = self._service.load_strategy_bundle(
                    self._snapshot,
                    sector_kind=self._sector_kind,
                    strategy_class=strategy_class or None,
                )
            else:
                bundle = self._service.load_continuation_bundle(
                    self._snapshot,
                    sector_kind=self._sector_kind,
                )
        except Exception as ex:
            if not self._cancelled:
                self.failed.emit(str(ex))
            else:
                self.failed.emit("")
            return
        if self._fail_if_cancelled():
            return
        self.finished.emit(bundle)


__all__ = ["SectorFlowOutlookLoadWorker", "_LOAD_CONTINUATION", "_LOAD_STRATEGY"]
