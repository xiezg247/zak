"""信息流同步 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.services.feed import FeedService


class FeedSyncWorker(QtCore.QThread):
    finished_with_result = QtCore.Signal(object)

    def __init__(self, service: FeedService, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def run(self) -> None:
        try:
            result = self._service.sync_all_enabled()
        except Exception as ex:
            result = JobResult(success=False, message=str(ex))
        self.finished_with_result.emit(result)
