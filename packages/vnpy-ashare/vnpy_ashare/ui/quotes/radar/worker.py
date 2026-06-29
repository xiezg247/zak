"""雷达页后台加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.radar.loaders import RadarCardData, incremental_refresh_radar_card_quotes, load_radar_cards_batch
from vnpy_ashare.quotes.radar.loaders.cancel import RadarLoadCancelled, bind_radar_load_cancel


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
        reset_cancel = bind_radar_load_cancel(lambda: self._cancelled)
        data: RadarCardData | None = None
        try:
            if self._quote_only and isinstance(self._existing_data, RadarCardData):
                data = incremental_refresh_radar_card_quotes(self._existing_data)
            else:
                loaded, errors = load_radar_cards_batch(
                    [(self._card_id, {"force_recompute": self._force_recompute})],
                    sector_variant=self._sector_variant,
                    sector_flow_hot_variant=self._sector_flow_hot_variant,
                    leader_pick_variant=self._leader_pick_variant,
                    limit_ladder_variant=self._limit_ladder_variant,
                    scenario_variant=self._scenario_variant,
                )
                if self._card_id in errors:
                    self.failed.emit(self._card_id, errors[self._card_id])
                    return
                data = loaded.get(self._card_id)
                if data is None:
                    self.failed.emit(self._card_id, f"雷达卡片加载失败：{self._card_id}")
                    return
        except RadarLoadCancelled:
            return
        except Exception as ex:
            self.failed.emit(self._card_id, str(ex))
            return
        finally:
            reset_cancel()
        if self._cancelled or data is None:
            return
        self.finished.emit(self._card_id, data, self._quote_only)


class RadarGroupLoadWorker(QtCore.QThread):
    """多张雷达卡片批量加载（共享 ScreeningContext + 并行）。"""

    finished = QtCore.Signal(object, object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        items: list[tuple[str, dict[str, object]]],
        sector_variant: str,
        sector_flow_hot_variant: str,
        leader_pick_variant: str,
        limit_ladder_variant: str,
        scenario_variant: str,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._items = list(items)
        self._sector_variant = sector_variant
        self._sector_flow_hot_variant = sector_flow_hot_variant
        self._leader_pick_variant = leader_pick_variant
        self._limit_ladder_variant = limit_ladder_variant
        self._scenario_variant = scenario_variant
        self._cancelled = False

    @property
    def card_ids(self) -> frozenset[str]:
        return frozenset(card_id for card_id, _kwargs in self._items)

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        reset_cancel = bind_radar_load_cancel(lambda: self._cancelled)
        try:
            loaded, errors = load_radar_cards_batch(
                self._items,
                sector_variant=self._sector_variant,
                sector_flow_hot_variant=self._sector_flow_hot_variant,
                leader_pick_variant=self._leader_pick_variant,
                limit_ladder_variant=self._limit_ladder_variant,
                scenario_variant=self._scenario_variant,
            )
        except RadarLoadCancelled:
            return
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        finally:
            reset_cancel()
        if self._cancelled:
            return
        self.finished.emit(loaded, errors)
