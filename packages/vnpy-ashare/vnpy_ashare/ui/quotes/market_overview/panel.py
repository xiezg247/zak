"""大盘概览面板：指数卡片 + 行业榜 + 市场广度。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market.index_amount import IndexAmountSeries
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.integrations.tushare.index_amount import DEFAULT_TRADING_DAYS
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot
from vnpy_ashare.quotes.market.market_environment import MarketEnvironmentSnapshot
from vnpy_ashare.quotes.market.market_overview_loaders import MarketOverviewData, SectorRankItem
from vnpy_ashare.ui.quotes.market_overview.index_amount_popup import IndexAmountPopup
from vnpy_ashare.ui.quotes.market_overview.index_amount_worker import IndexAmountLoadWorker
from vnpy_ashare.ui.quotes.market_overview.index_card import IndexCardWidget
from vnpy_ashare.ui.quotes.market_overview.sector_card import SectorCardWidget
from vnpy_ashare.ui.quotes.market_overview.stats_bar import MarketStatsBar
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active
from vnpy_common.ui.theme.manager import theme_manager

_TAB_INDEX = 0
_TAB_SECTOR = 1
_CARD_STRIP_HEIGHT = 76


class MarketOverviewPanel(QtWidgets.QWidget):
    """市场页顶部大盘概览带。"""

    sector_selected = QtCore.Signal(str)
    sector_flow_requested = QtCore.Signal()
    refresh_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketOverviewPanel")
        self._active_industry: str | None = None
        self._last_sectors: list[SectorRankItem] = []

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stats_bar = MarketStatsBar(self)
        self._stats_bar.set_loading()
        self._stats_bar.refresh_requested.connect(self.refresh_requested.emit)
        root.addWidget(self._stats_bar)

        toolbar_host = QtWidgets.QWidget(self)
        toolbar_host.setObjectName("MarketOverviewToolbar")
        toolbar = QtWidgets.QHBoxLayout(toolbar_host)
        toolbar.setContentsMargins(12, 2, 12, 4)
        toolbar.setSpacing(8)

        toolbar.addStretch(1)

        tab_group = QtWidgets.QHBoxLayout()
        tab_group.setSpacing(4)
        self._tab_index_btn = QtWidgets.QPushButton("指数")
        self._tab_index_btn.setObjectName("OverviewTabButton")
        self._tab_index_btn.setCheckable(True)
        self._tab_index_btn.setChecked(True)
        self._tab_sector_btn = QtWidgets.QPushButton("申万行业")
        self._tab_sector_btn.setObjectName("OverviewTabButton")
        self._tab_sector_btn.setCheckable(True)
        self._tab_sector_btn.setToolTip("申万 2021 行业榜（L2）；卡片首行标注 L1 一级行业")
        tab_group.addWidget(self._tab_index_btn)
        tab_group.addWidget(self._tab_sector_btn)
        toolbar.addLayout(tab_group)

        self._sector_flow_btn = QtWidgets.QPushButton("板块资金")
        self._sector_flow_btn.setObjectName("SecondaryButton")
        self._sector_flow_btn.setToolTip("打开板块资金行业榜")
        self._sector_flow_btn.clicked.connect(self.sector_flow_requested.emit)
        toolbar.addWidget(self._sector_flow_btn)

        self._tab_button_group = QtWidgets.QButtonGroup(self)
        self._tab_button_group.setExclusive(True)
        self._tab_button_group.addButton(self._tab_index_btn, _TAB_INDEX)
        self._tab_button_group.addButton(self._tab_sector_btn, _TAB_SECTOR)
        root.addWidget(toolbar_host)

        self._stack = QtWidgets.QStackedWidget(self)
        self._stack.setObjectName("OverviewStack")

        self._index_scroll = self._build_index_scroll()
        self._sector_scroll = self._build_sector_scroll()
        self._stack.addWidget(self._index_scroll)
        self._stack.addWidget(self._sector_scroll)
        root.addWidget(self._stack)

        self._tab_button_group.idClicked.connect(self._switch_tab)

        self._index_cards: dict[str, IndexCardWidget] = {}
        self._sector_cards: dict[str, SectorCardWidget] = {}
        self._amount_popup = IndexAmountPopup(self.window())
        self._amount_worker: IndexAmountLoadWorker | None = None
        self._amount_retired_workers: list[QtCore.QThread] = []
        self._amount_anchor: IndexCardWidget | None = None
        self._amount_series_cache: dict[str, IndexAmountSeries] = {}
        theme_manager().register_callback(self._on_theme_changed)

    def _build_index_scroll(self) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("IndexCardScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setFixedHeight(_CARD_STRIP_HEIGHT)

        self._cards_host = QtWidgets.QWidget()
        self._cards_host.setObjectName("IndexCardHost")
        self._cards_layout = QtWidgets.QHBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(12, 4, 12, 8)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch(1)
        scroll.setWidget(self._cards_host)
        return scroll

    def _build_sector_scroll(self) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("SectorCardScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setFixedHeight(_CARD_STRIP_HEIGHT)

        self._sector_host = QtWidgets.QWidget()
        self._sector_host.setObjectName("SectorCardHost")
        self._sector_layout = QtWidgets.QHBoxLayout(self._sector_host)
        self._sector_layout.setContentsMargins(12, 4, 12, 8)
        self._sector_layout.setSpacing(8)
        self._sector_layout.addStretch(1)

        self._sector_empty = QtWidgets.QLabel(
            "暂无行业榜（请配置 TUSHARE_TOKEN，并运行「后台 → 定时任务 → 同步行业映射」）"
        )
        self._sector_empty.setObjectName("SectorCardEmpty")
        self._sector_layout.insertWidget(0, self._sector_empty)

        scroll.setWidget(self._sector_host)
        return scroll

    def _switch_tab(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._tab_index_btn.setChecked(index == _TAB_INDEX)
        self._tab_sector_btn.setChecked(index == _TAB_SECTOR)

    def _on_theme_changed(self, _tokens) -> None:
        self._stats_bar.refresh_theme()

    def apply_data(self, data: MarketOverviewData, *, session_note: str = "") -> None:
        self._sync_index_cards(data.indices)
        self.apply_sectors(data.sectors)
        self.apply_environment(data.environment)
        if data.breadth is not None:
            self._last_breadth = data.breadth
            self._stats_bar.render_breadth(data.breadth, session_note=session_note)
        elif not hasattr(self, "_last_breadth"):
            self._stats_bar.set_empty()

    def apply_breadth(self, breadth: MarketBreadthSnapshot, *, session_note: str = "") -> None:
        self._last_breadth = breadth
        self._stats_bar.render_breadth(breadth, session_note=session_note)

    def apply_emotion_cycle(self, snapshot: EmotionCycleSnapshot | None) -> None:
        self._stats_bar.render_emotion_cycle(snapshot)

    def apply_sectors(self, sectors: list[SectorRankItem]) -> None:
        self._last_sectors = list(sectors)
        self._sync_sector_cards(sectors)
        self._sync_sector_selection()

    def top_sector_industries(self, *, limit: int = 6) -> list[str]:
        names: list[str] = []
        for item in self._last_sectors:
            if item.industry and item.industry not in names:
                names.append(item.industry)
            if len(names) >= limit:
                break
        return names

    def set_industry_filter(self, industry: str | None) -> None:
        self._active_industry = industry
        if industry:
            self._switch_tab(_TAB_SECTOR)
        self._sync_sector_selection()

    def _sync_sector_selection(self) -> None:
        active = self._active_industry
        for key, card in self._sector_cards.items():
            card.set_selected(active is not None and key == active)

    def apply_environment(self, env: MarketEnvironmentSnapshot | None) -> None:
        self._last_environment = env
        self._stats_bar.render_environment(env)

    def set_overview_refreshing(self, refreshing: bool) -> None:
        self._stats_bar.set_refreshing(refreshing)

    def _sync_index_cards(self, indices: list[tuple[str, QuoteSnapshot]]) -> None:
        seen: set[str] = set()
        for label, quote in indices:
            tf_symbol = quote.symbol
            seen.add(tf_symbol)
            card = self._index_cards.get(tf_symbol)
            if card is None:
                card = IndexCardWidget(label, quote, parent=self._cards_host)
                card.amount_popup_requested.connect(self._on_index_amount_popup)
                self._index_cards[tf_symbol] = card
                insert_at = max(self._cards_layout.count() - 1, 0)
                self._cards_layout.insertWidget(insert_at, card)
            else:
                card.update_quote(label, quote)

        for tf_symbol in list(self._index_cards):
            if tf_symbol not in seen:
                card = self._index_cards.pop(tf_symbol)
                self._cards_layout.removeWidget(card)
                card.deleteLater()

    def _sync_sector_cards(self, sectors: list[SectorRankItem]) -> None:
        has_sectors = bool(sectors)
        self._sector_empty.setVisible(not has_sectors)

        seen: set[str] = set()
        for item in sectors:
            key = item.industry
            seen.add(key)
            card = self._sector_cards.get(key)
            if card is None:
                card = SectorCardWidget(item, parent=self._sector_host)
                card.activated.connect(self.sector_selected.emit)
                self._sector_cards[key] = card
                insert_at = max(self._sector_layout.count() - 1, 0)
                self._sector_layout.insertWidget(insert_at, card)
            else:
                card.update_item(item)

        for key in list(self._sector_cards):
            if key not in seen:
                card = self._sector_cards.pop(key)
                self._sector_layout.removeWidget(card)
                card.deleteLater()
        self._sync_sector_selection()

    def _on_index_amount_popup(self, ts_code: str, label: str) -> None:
        anchor = self._index_cards.get(ts_code)
        if anchor is None:
            return
        self._amount_anchor = anchor
        cached = self._amount_series_cache.get(ts_code)
        self._amount_popup.show_loading(label=label, trading_days=DEFAULT_TRADING_DAYS)
        self._amount_popup.show_near(anchor)
        if cached is not None:
            self._amount_popup.render_series(cached, trading_days=DEFAULT_TRADING_DAYS)
            return
        if thread_is_active(self._amount_worker):
            return
        worker = IndexAmountLoadWorker(ts_code, label=label, parent=self)
        self._amount_worker = worker

        def on_finished(series) -> None:
            if self._amount_worker is worker:
                self._amount_worker = None
            release_thread(self._amount_retired_workers, worker)
            if series.ts_code:
                self._amount_series_cache[series.ts_code] = series
            if self._amount_anchor is not None and self._amount_anchor.tf_symbol == series.ts_code:
                self._amount_popup.render_series(series, trading_days=DEFAULT_TRADING_DAYS)
                self._amount_popup.show_near(self._amount_anchor)

        def on_failed(message: str) -> None:
            if self._amount_worker is worker:
                self._amount_worker = None
            release_thread(self._amount_retired_workers, worker)
            if self._amount_anchor is not None:
                self._amount_popup.show_error(
                    label=label,
                    trading_days=DEFAULT_TRADING_DAYS,
                    message=message,
                )
                self._amount_popup.show_near(self._amount_anchor)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()
