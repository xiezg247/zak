"""诊断分析后台 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore


class DiagnoseWorker(QtCore.QThread):
    """后台调用 AnalysisService.diagnose。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        analysis_service,
        *,
        vt_symbol: str,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.analysis_service = analysis_service
        self.vt_symbol = vt_symbol

    def run(self) -> None:
        try:
            result = self.analysis_service.diagnose(self.vt_symbol)
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex))
