"""雷达页后台加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData, incremental_refresh_radar_card_quotes, load_radar_card


class RadarCardLoadWorker(QtCore.QThread):
    """单张雷达卡片后台加载。"""

    finished = QtCore.Signal(str, object, bool)
    failed = QtCore.Signal(str, str)

    def __init__(
        self,
        *,
        card_id: str,
        sector_variant: str,
        sector_flow_hot_variant: str,
        leader_pick_variant: str,
        limit_ladder_variant: str,
        scenario_variant: str,
        force_recompute: bool = False,
        quote_only: bool = False,
        existing_data: object | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._card_id = card_id
        self._sector_variant = sector_variant
        self._sector_flow_hot_variant = sector_flow_hot_variant
        self._leader_pick_variant = leader_pick_variant
        self._limit_ladder_variant = limit_ladder_variant
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
            if self._quote_only and isinstance(self._existing_data, RadarCardData):
                data = incremental_refresh_radar_card_quotes(self._existing_data)
            else:
                data = load_radar_card(
                    self._card_id,
                    sector_variant=self._sector_variant,
                    sector_flow_hot_variant=self._sector_flow_hot_variant,
                    leader_pick_variant=self._leader_pick_variant,
                    limit_ladder_variant=self._limit_ladder_variant,
                    scenario_variant=self._scenario_variant,
                    force_recompute=self._force_recompute,
                )
        except Exception as ex:
            self.failed.emit(self._card_id, str(ex))
            return
        if self._cancelled:
            return
        self.finished.emit(self._card_id, data, self._quote_only)
