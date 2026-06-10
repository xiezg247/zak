"""选股页 Qt Worker（后台执行选股 / 配方 / 批量操作）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.screener.batch_actions import batch_download_daily_bars, run_batch_backtests
from vnpy_ashare.screener.recipe_runner import run_recipe_object
from vnpy_ashare.screener.runner import ScreenerRequest, resolve_preset_input, run_screener


class ScreenerRunWorker(QtCore.QThread):
    """后台执行 preset / 已保存方案选股；finished 发射 ScreenerRunResult。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        preset: str,
        top_n: int,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        min_turnover: float | None = None,
        scheme_id: str | None = None,
    ) -> None:
        super().__init__()
        self.preset = preset
        self.top_n = top_n
        self.min_change_pct = min_change_pct
        self.max_change_pct = max_change_pct
        self.min_turnover = min_turnover
        self.scheme_id = scheme_id
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            if self.scheme_id:
                request = ScreenerRequest(
                    preset="",
                    top_n=self.top_n,
                    scheme_id=self.scheme_id,
                )
            elif self.preset.startswith("我的 · "):
                request = resolve_preset_input(self.preset)
                request.top_n = self.top_n
            else:
                request = ScreenerRequest(
                    preset=self.preset,
                    top_n=self.top_n,
                    min_change_pct=self.min_change_pct,
                    max_change_pct=self.max_change_pct,
                    min_turnover=self.min_turnover,
                )
            result = run_screener(request)
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(result)
        except Exception as ex:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.failed.emit(str(ex))


class ScreenerRecipeRunWorker(QtCore.QThread):
    """后台执行多因子配方；finished 发射 (ScreenerRunResult, recipe_id)。"""

    finished = QtCore.Signal(object, str)
    failed = QtCore.Signal(str)

    def __init__(self, recipe, recipe_id: str, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.recipe = recipe
        self.recipe_id = recipe_id
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            result = run_recipe_object(self.recipe, condition_prefix="配方")
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(result, self.recipe_id)
        except Exception as ex:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.failed.emit(str(ex))


class ScreenerBatchDownloadWorker(QtCore.QThread):
    """后台对选股结果批量下载日 K；finished 发射 JobResult。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, rows: list[dict], parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.rows = rows
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            result = batch_download_daily_bars(
                self.rows,
                should_cancel=lambda: self._cancel_requested,
            )
            if self._cancel_requested or "已取消" in result.message:
                self.failed.emit("已取消")
                return
            self.finished.emit(result)
        except Exception as ex:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.failed.emit(str(ex))


class ScreenerBatchBacktestWorker(QtCore.QThread):
    """后台对选股结果批量回测；finished 发射 list[BatchBacktestRow]。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        main_engine,
        rows: list[dict],
        params,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.main_engine = main_engine
        self.rows = rows
        self.params = params

    def run(self) -> None:
        try:
            results = run_batch_backtests(self.main_engine, self.rows, self.params)
            self.finished.emit(results)
        except Exception as ex:
            self.failed.emit(str(ex))
