"""选股页 Qt Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore


class ScreenerRunWorker(QtCore.QThread):
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

    def run(self) -> None:
        try:
            from vnpy_ashare.screener.runner import ScreenerRequest, resolve_preset_input, run_screener

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
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex))


class ScreenerRecipeRunWorker(QtCore.QThread):
    finished = QtCore.Signal(object, str)
    failed = QtCore.Signal(str)

    def __init__(self, recipe, recipe_id: str, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.recipe = recipe
        self.recipe_id = recipe_id

    def run(self) -> None:
        try:
            from vnpy_ashare.screener.recipe_runner import run_recipe_object

            result = run_recipe_object(self.recipe, condition_prefix="配方")
            self.finished.emit(result, self.recipe_id)
        except Exception as ex:
            self.failed.emit(str(ex))


class ScreenerBatchDownloadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, rows: list[dict], parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.rows = rows

    def run(self) -> None:
        try:
            from vnpy_ashare.screener.batch_actions import batch_download_daily_bars

            result = batch_download_daily_bars(self.rows)
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex))


class ScreenerBatchBacktestWorker(QtCore.QThread):
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
            from vnpy_ashare.screener.batch_actions import run_batch_backtests

            results = run_batch_backtests(self.main_engine, self.rows, self.params)
            self.finished.emit(results)
        except Exception as ex:
            self.failed.emit(str(ex))
