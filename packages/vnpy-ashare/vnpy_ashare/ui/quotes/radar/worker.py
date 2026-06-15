"""雷达页后台加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.radar.radar_loaders import incremental_refresh_radar_card_quotes, load_radar_board, load_radar_card


class RadarCardLoadWorker(QtCore.QThread):
    """单张雷达卡片后台加载。"""

    finished = QtCore.Signal(str, object, bool)
    failed = QtCore.Signal(str, str)

    def __init__(
        self,
        *,
        card_id: str,
        screen_task_variant: str,
        sector_variant: str,
        scenario_variant: str,
        force_recompute: bool = False,
        quote_only: bool = False,
        existing_data: object | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._card_id = card_id
        self._screen_task_variant = screen_task_variant
        self._sector_variant = sector_variant
        self._scenario_variant = scenario_variant
        self._force_recompute = force_recompute
        self._quote_only = quote_only
        self._existing_data = existing_data
        self._cancelled = False

    @property
    def card_id(self) -> str:
        return self._card_id

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            if self._quote_only and self._existing_data is not None:
                data = incremental_refresh_radar_card_quotes(self._existing_data)
            else:
                data = load_radar_card(
                    self._card_id,
                    screen_task_variant=self._screen_task_variant,
                    sector_variant=self._sector_variant,
                    scenario_variant=self._scenario_variant,
                    force_recompute=self._force_recompute,
                )
        except Exception as ex:
            self.failed.emit(self._card_id, str(ex))
            return
        if self._cancelled:
            return
        self.finished.emit(self._card_id, data, self._quote_only)


class RadarBoardLoadWorker(QtCore.QThread):
    """兼容：一次性加载全部雷达卡片。"""

    finished = QtCore.Signal(dict)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        screen_task_variant: str,
        sector_variant: str,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._screen_task_variant = screen_task_variant
        self._sector_variant = sector_variant
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            payload = load_radar_board(
                screen_task_variant=self._screen_task_variant,
                sector_variant=self._sector_variant,
            )
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        if self._cancelled:
            return
        self.finished.emit(payload)
