"""选股 hub：条件选股 + 多因子配方。"""

from __future__ import annotations

from typing import Literal

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.events import FillRecipeRequest, FillScreenerRequest
from vnpy_ashare.screener.run.run_store import get_run, is_auto_run
from vnpy_common.ui.panel_widgets import configure_document_tab_widget

from .auto_screener_page import AutoScreenerPageWidget
from .screener_page import ScreenerPageWidget

TabKey = Literal["condition", "recipe"]


class ScreenerHubPageWidget(QtWidgets.QWidget):
    """左侧导航「选股」页：内嵌条件选股与多因子配方两个 Tab。"""

    open_scheduler_requested = QtCore.Signal()

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")
        self._active = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = configure_document_tab_widget(QtWidgets.QTabWidget())
        self._tabs.setDocumentMode(True)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._condition_page = ScreenerPageWidget(main_engine, event_engine, embedded=True)
        self._recipe_page = AutoScreenerPageWidget(main_engine, event_engine, embedded=True)
        self._recipe_page.open_scheduler_requested.connect(self.open_scheduler_requested.emit)

        self._tabs.addTab(self._condition_page, "条件选股")
        self._tabs.addTab(self._recipe_page, "多因子配方")
        layout.addWidget(self._tabs)

    @property
    def condition_page(self) -> ScreenerPageWidget:
        return self._condition_page

    @property
    def recipe_page(self) -> AutoScreenerPageWidget:
        return self._recipe_page

    def _on_tab_changed(self, _index: int) -> None:
        if not self._active:
            return
        self._condition_page.deactivate()
        self._recipe_page.deactivate()
        self._current_page().activate()

    def _current_page(self) -> ScreenerPageWidget | AutoScreenerPageWidget:
        return self._recipe_page if self._tabs.currentIndex() == 1 else self._condition_page

    def select_tab(self, tab: TabKey) -> None:
        index = 1 if tab == "recipe" else 0
        self._tabs.setCurrentIndex(index)

    def _resolve_tab(self, run_id: str, page_key: str | None) -> TabKey:
        if page_key == "auto_screener":
            return "recipe"
        if page_key == "screener":
            return "condition"
        record = get_run(run_id)
        if record is not None and is_auto_run(record.config):
            return "recipe"
        return "condition"

    def apply_request(self, data: FillScreenerRequest) -> None:
        self.select_tab("condition")
        self._condition_page.apply_request(data)

    def apply_recipe_request(self, data: FillRecipeRequest) -> None:
        self.select_tab("recipe")
        self._recipe_page.apply_recipe_request(data)

    def run_industry_screen(self, industry: str) -> None:
        self.select_tab("condition")
        self._condition_page.run_industry_screen(industry)

    def run_radar_resonance_screen(self) -> None:
        self.select_tab("condition")
        self._condition_page.run_radar_resonance_screen()

    def run_leader_screen(self, *, variant: str = "mainline") -> None:
        self.select_tab("condition")
        self._condition_page.run_leader_screen(variant=variant)

    def show_historical_run(self, run_id: str, *, page_key: str | None = None) -> None:
        tab = self._resolve_tab(run_id, page_key)
        self.select_tab(tab)
        if tab == "recipe":
            self._recipe_page.show_historical_run(run_id)
        else:
            self._condition_page.show_historical_run(run_id)

    def on_scheduled_run_complete(self, job_id: str, message: str) -> None:
        self.select_tab("recipe")
        self._recipe_page.on_scheduled_run_complete(job_id, message)

    def activate(self) -> None:
        self._active = True
        self._current_page().activate()

    def deactivate(self) -> None:
        self._active = False
        self._condition_page.deactivate()
        self._recipe_page.deactivate()
