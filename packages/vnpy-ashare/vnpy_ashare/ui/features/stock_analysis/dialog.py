"""个股分析对话框。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.context.quote.prompts import build_diagnose_ai_prompt
from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.ai.llm_bridge import get_llm_engine
from vnpy_ashare.app.engine_access import get_quote_service, get_stock_analysis_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.format import EMPTY_DISPLAY, format_amount, format_volume
from vnpy_ashare.services.stock.context import build_analysis_ai_context, format_technical_summary
from vnpy_ashare.ui.features.notes_center.report_launcher import open_notes_reports_center
from vnpy_ashare.ui.features.stock_analysis.ai_sidebar import StockAnalysisAiSidebar
from vnpy_ashare.ui.features.stock_analysis.capital_tab import CapitalAnalysisTab
from vnpy_ashare.ui.features.stock_analysis.chart_tab import StockAnalysisChartTab
from vnpy_ashare.ui.features.stock_analysis.concept_tab import ConceptAnalysisTab
from vnpy_ashare.ui.features.stock_analysis.events_tab import EventsAnalysisTab
from vnpy_ashare.ui.features.stock_analysis.financial_tab import FinancialAnalysisTab
from vnpy_ashare.ui.features.stock_analysis.holders_tab import HoldersAnalysisTab
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost
from vnpy_ashare.ui.features.stock_analysis.overview_panel import OverviewAnalysisPanel
from vnpy_ashare.ui.features.stock_analysis.sector_tab import SectorAnalysisTab
from vnpy_ashare.ui.features.stock_analysis.short_term_tab import ShortTermAnalysisTab
from vnpy_ashare.ui.features.stock_analysis.worker import (
    StockAnalysisPayload,
    StockAnalysisScope,
    StockAnalysisWorker,
)
from vnpy_ashare.ui.shell.main_window_lookup import find_ashare_main_window
from vnpy_common.ui.dialog_shell import (
    apply_standard_dialog_layout,
    build_panel_footer,
    set_panel_status_loading,
    setup_responsive_dialog,
)
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.loading_overlay import LoadingContentHost
from vnpy_common.ui.panel_widgets import MetricTile, configure_document_tab_widget, content_card, panel_status_label, section_title, tab_page
from vnpy_common.ui.qt_helpers import release_thread
from vnpy_common.ui.theme.build_panel import build_stock_analysis_stylesheet
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_TAB_OVERVIEW = 0
_TAB_SHORT_TERM = 1
_TAB_CHART = 2
_TAB_SECTOR = 3
_TAB_CONCEPT = 4
_TAB_CAPITAL = 5
_TAB_EVENTS = 6
_TAB_HOLDERS = 7
_TAB_FINANCIAL = 8

_TAB_SCOPES: dict[int, StockAnalysisScope] = {
    _TAB_OVERVIEW: "overview",
    _TAB_SHORT_TERM: "short_term",
    _TAB_SECTOR: "sector",
    _TAB_CONCEPT: "concept",
    _TAB_CAPITAL: "capital",
    _TAB_EVENTS: "events",
    _TAB_HOLDERS: "holders",
    _TAB_FINANCIAL: "financial",
}

_JUMP_TAB_INDEX: dict[str, int] = {
    "chart": _TAB_CHART,
    "short_term": _TAB_SHORT_TERM,
    "sector": _TAB_SECTOR,
    "concept": _TAB_CONCEPT,
    "capital": _TAB_CAPITAL,
    "events": _TAB_EVENTS,
    "holders": _TAB_HOLDERS,
    "financial": _TAB_FINANCIAL,
}

_SCOPE_STATUS: dict[StockAnalysisScope, str] = {
    "overview": "正在加载本地概览…",
    "short_term": "正在加载短线档案（含涨停史与龙虎榜）…",
    "sector": "正在加载板块与估值…",
    "concept": "正在加载概念题材…",
    "capital": "正在加载资金流…",
    "events": "正在加载事件日历…",
    "holders": "正在加载股东结构…",
    "financial": "正在同步财报…",
}


def _quote_header_meta(quote: QuoteSnapshot | None, item: StockItem) -> dict[str, str]:
    name = quote.name if quote and quote.name else item.name
    symbol = item.symbol
    vt_symbol = item.vt_symbol
    if quote is None or quote.last_price <= 0:
        return {
            "name": name or vt_symbol,
            "symbol": symbol,
            "vt_symbol": vt_symbol,
            "price": "—",
            "change": "",
            "change_color": "",
            "change_bg": "",
        }
    change_color = pct_change_color(quote.change_pct, theme_manager().tokens())
    bg = "rgba(255,80,80,0.12)" if quote.change_pct < 0 else "rgba(80,200,120,0.12)"
    if quote.change_pct == 0:
        bg = "rgba(120,120,130,0.12)"
    return {
        "name": name or vt_symbol,
        "symbol": symbol,
        "vt_symbol": vt_symbol,
        "price": f"{quote.last_price:.2f}",
        "change": f"{quote.change_amount:+.2f}  ({quote.change_pct:+.2f}%)",
        "change_color": change_color,
        "change_bg": bg,
    }


class StockAnalysisDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        item: StockItem,
        host: StockAnalysisHost,
        quote: QuoteSnapshot | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StockAnalysisDialog")
        self._item = item
        self._host = host
        self._quote = quote
        self._worker: StockAnalysisWorker | None = None
        self._payload: StockAnalysisPayload | None = None
        self._closing = False
        self._chart_loaded = False
        self._loaded_scopes: set[StockAnalysisScope] = set()
        self._loading_scope: StockAnalysisScope | None = None
        self._pending_scopes: list[StockAnalysisScope] = []

        meta = _quote_header_meta(quote, item)
        self.setWindowTitle(f"个股分析 · {meta['name']}")
        setup_responsive_dialog(
            self,
            parent,
            min_width=1320,
            min_height=920,
            width_ratio=0.92,
            height_ratio=0.94,
            max_width=1720,
            max_height=1200,
        )

        header = self._build_header(meta)
        self._status_label = panel_status_label("就绪")
        tabs = self._build_tabs()
        self._content_host = LoadingContentHost(tabs)
        self._ai_sidebar = StockAnalysisAiSidebar(self._host, self)
        self._body_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self._body_splitter.setObjectName("StockAnalysisBodySplitter")
        self._body_splitter.setChildrenCollapsible(False)
        self._body_splitter.addWidget(self._content_host)
        self._body_splitter.addWidget(self._ai_sidebar)
        self._body_splitter.setStretchFactor(0, 1)
        self._body_splitter.setStretchFactor(1, 0)
        self._body_splitter.setCollapsible(0, False)
        self._body_splitter.setCollapsible(1, True)
        self._ai_sidebar.attach_splitter(self._body_splitter)
        self._ai_sidebar.collapse()
        footer = self._build_footer()

        apply_standard_dialog_layout(
            self,
            header=header,
            content=self._body_splitter,
            footer=footer,
        )

        theme_manager().bind_stylesheet(self, extra=build_stock_analysis_stylesheet)
        self._refresh_live_quote()
        self._init_idle_tabs()
        self._ensure_tab_data(_TAB_OVERVIEW, sync_financials=True)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._refresh_live_quote()
        main = self._find_ashare_main_window()
        if main is not None:
            main.register_floating_overlay(self)
        self._publish_ai_context()
        llm_engine = get_llm_engine(self._host.main_engine)
        if llm_engine is not None and self._host.source_page != "AI 助手":
            self._ai_sidebar.bind_engine(llm_engine)
        elif self._host.source_page == "AI 助手":
            self._ai_btn.setToolTip("在 AI 助手全屏页解读（避免与当前页重复挂载对话面板）")

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._ai_sidebar.is_expanded():
            self._ai_sidebar.expand()
        main = self._find_ashare_main_window()
        if main is not None:
            main.on_floating_overlay_resized(self)

    def _find_ashare_main_window(self) -> Any | None:
        return find_ashare_main_window(self)

    def _init_idle_tabs(self) -> None:
        self._short_term_tab.show_idle()
        self._sector_tab.show_idle()
        self._concept_tab.show_idle()
        self._capital_tab.show_idle()
        self._events_tab.show_idle()
        self._holders_tab.show_idle()
        self._financial_tab.show_idle()

    def _build_header(self, meta: dict[str, str]) -> QtWidgets.QWidget:
        header = QtWidgets.QWidget()
        header.setObjectName("StockAnalysisHeader")
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(2)
        symbol_label = QtWidgets.QLabel(meta["symbol"])
        symbol_label.setObjectName("StockAnalysisSymbol")
        name_label = QtWidgets.QLabel(meta["name"])
        name_label.setObjectName("StockAnalysisName")
        code_label = QtWidgets.QLabel(meta["vt_symbol"])
        code_label.setObjectName("StockAnalysisCode")
        left.addWidget(symbol_label)
        left.addWidget(name_label)
        left.addWidget(code_label)

        right = QtWidgets.QVBoxLayout()
        right.setSpacing(4)
        right.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        price_label = QtWidgets.QLabel(meta["price"])
        price_label.setObjectName("StockAnalysisPrice")
        if meta["change_color"]:
            price_label.setStyleSheet(f"color: {meta['change_color']};")
        change_label = QtWidgets.QLabel(meta["change"])
        change_label.setObjectName("StockAnalysisChange")
        if meta["change_color"]:
            change_label.setStyleSheet(f"color: {meta['change_color']}; background-color: {meta['change_bg']};")
        right.addWidget(price_label)
        if meta["change"]:
            right.addWidget(change_label)

        row.addLayout(left, stretch=1)
        row.addLayout(right)
        return header

    def _build_tabs(self) -> QtWidgets.QTabWidget:
        self._overview_panel = OverviewAnalysisPanel()
        self._overview_panel.jump_requested.connect(self._jump_from_overview)

        overview_page = tab_page(
            self._build_quote_metrics_section(),
            self._overview_panel,
            stretch_index=1,
        )

        self._chart_tab = StockAnalysisChartTab()
        self._chart_tab.set_retired_workers(self._host.retired_workers)
        self._short_term_tab = ShortTermAnalysisTab()
        self._short_term_tab.peer_activated.connect(self._open_peer_analysis)
        self._sector_tab = SectorAnalysisTab()
        self._sector_tab.peer_activated.connect(self._open_peer_analysis)
        self._concept_tab = ConceptAnalysisTab()
        self._capital_tab = CapitalAnalysisTab()
        self._events_tab = EventsAnalysisTab()
        self._holders_tab = HoldersAnalysisTab()
        self._financial_tab = FinancialAnalysisTab()

        tabs = configure_document_tab_widget(QtWidgets.QTabWidget())
        tabs.addTab(overview_page, "概览")
        tabs.addTab(self._short_term_tab, "短线")
        tabs.addTab(tab_page(self._chart_tab, margins=(0, 4, 0, 0)), "图表")
        tabs.addTab(self._sector_tab, "板块")
        tabs.addTab(self._concept_tab, "概念")
        tabs.addTab(self._capital_tab, "资金")
        tabs.addTab(self._events_tab, "事件")
        tabs.addTab(self._holders_tab, "股东")
        tabs.addTab(self._financial_tab, "财务")
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs
        return tabs

    def _open_peer_analysis(self, vt_symbol: str, name: str) -> None:
        if not vt_symbol or vt_symbol == self._item.vt_symbol:
            return
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            return
        if name and not item.name:
            item = StockItem(symbol=item.symbol, exchange=item.exchange, name=name)
        quote = self._host.quote_for_item(item)
        peer = StockAnalysisDialog(item=item, host=self._host, quote=quote, parent=self)
        peer.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        peer.show()

    def _build_quote_metrics_section(self) -> QtWidgets.QWidget:
        self._quote_tiles = {
            "last": MetricTile("现价"),
            "change": MetricTile("涨跌"),
            "ohlc": MetricTile("今开 / 最高 / 最低"),
            "volume": MetricTile("成交量"),
            "amount": MetricTile("成交额"),
            "turnover": MetricTile("换手率"),
            "amplitude": MetricTile("振幅"),
            "time": MetricTile("更新时间"),
        }
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        positions = [
            ("last", 0, 0),
            ("change", 0, 1),
            ("ohlc", 0, 2),
            ("volume", 0, 3),
            ("amount", 1, 0),
            ("turnover", 1, 1),
            ("amplitude", 1, 2),
            ("time", 1, 3),
        ]
        for key, row, col in positions:
            tile = self._quote_tiles[key]
            tile.setMinimumWidth(132)
            tile.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            grid.addWidget(tile, row, col)
        for col in range(4):
            grid.setColumnStretch(col, 1)

        wrapper = QtWidgets.QWidget()
        wrapper.setLayout(grid)
        return content_card(section_title("实时行情"), wrapper, margins=(8, 8, 8, 8))

    def _build_footer(self) -> QtWidgets.QWidget:
        self._refresh_btn = QtWidgets.QPushButton("刷新")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.clicked.connect(self._refresh_current_tab)
        self._ai_btn = QtWidgets.QPushButton("问 AI 解读")
        self._ai_btn.setObjectName("ActionButton")
        self._ai_btn.setToolTip("在右侧 AI 侧栏解读；完成后可存为分析报告或追加流水")
        self._ai_btn.clicked.connect(self._ask_ai)
        self._reports_btn = QtWidgets.QPushButton("历史报告")
        self._reports_btn.setObjectName("SecondaryButton")
        self._reports_btn.clicked.connect(self._open_reports_center)
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.close)
        return build_panel_footer(
            self._status_label,
            self._refresh_btn,
            self._reports_btn,
            self._ai_btn,
            close_btn,
        )

    def closeEvent(self, event) -> None:
        self._closing = True
        self._ai_sidebar.deactivate()
        main = self._find_ashare_main_window()
        if main is not None:
            main.unregister_floating_overlay(self)
        self._chart_tab.shutdown()
        if self._worker is not None:
            release_thread(self._host.retired_workers, self._worker, timeout_ms=1500)
            self._worker = None
        super().closeEvent(event)

    def _on_tab_changed(self, index: int) -> None:
        if index == _TAB_CHART:
            self._ensure_chart_loaded()
            return
        self._ensure_tab_data(index)

    def _ensure_chart_loaded(self) -> None:
        if self._chart_loaded or self._closing:
            return
        self._chart_loaded = True
        self._chart_tab.load(self._item, quote=self._quote)

    def _ensure_tab_data(self, index: int, *, sync_financials: bool = False) -> None:
        scope = _TAB_SCOPES.get(index)
        if scope is None or scope in self._loaded_scopes:
            return
        self._start_load(scope=scope, sync_financials=sync_financials)

    def _refresh_current_tab(self) -> None:
        self._refresh_live_quote()
        index = self._tabs.currentIndex()
        if index == _TAB_CHART:
            self._chart_loaded = False
            self._ensure_chart_loaded()
            self._status_label.setText("图表已刷新")
            return

        scope = _TAB_SCOPES.get(index)
        if scope is None:
            return
        self._loaded_scopes.discard(scope)
        sync = scope == "financial"
        self._start_load(scope=scope, sync_financials=sync, force=True)

    def _stock_analysis_service(self):
        return get_stock_analysis_service(self._host.main_engine)

    def _analysis_service(self):
        service = self._stock_analysis_service()
        return service.engine.analysis_service if service is not None else None

    def _financial_service(self):
        service = self._stock_analysis_service()
        return service.engine.financial_service if service is not None else None

    def _quote_summary(self) -> dict[str, Any]:
        quote = self._quote
        if quote is None:
            return {}
        return {
            "last_price": quote.last_price,
            "change_pct": quote.change_pct,
            "change_amount": quote.change_amount,
            "open_price": quote.open_price,
            "high_price": quote.high_price,
            "low_price": quote.low_price,
            "volume": quote.volume,
            "amount": quote.amount,
            "turnover_rate": quote.turnover_rate,
            "amplitude": quote.amplitude,
            "trade_time": quote.trade_time,
        }

    def _refresh_live_quote(self) -> None:
        quote = self._host.quote_for_item(self._item)
        if quote is None:
            return
        self._quote = quote
        self._render_quote_metrics()

    def _render_quote_metrics(self) -> None:
        quote = self._quote
        tiles = self._quote_tiles
        if quote is None:
            for tile in tiles.values():
                tile.set_value("—")
            tiles["time"].set_value("暂无行情")
            return

        change_color = pct_change_color(quote.change_pct, theme_manager().tokens())
        tiles["last"].set_value(f"{quote.last_price:.2f}", color=change_color)
        tiles["change"].set_value(
            f"{quote.change_amount:+.2f}",
            subtitle=f"{quote.change_pct:+.2f}%",
            color=change_color,
        )
        open_text = f"{quote.open_price:.2f}" if quote.open_price > 0 else EMPTY_DISPLAY
        high_text = f"{quote.high_price:.2f}" if quote.high_price > 0 else EMPTY_DISPLAY
        low_text = f"{quote.low_price:.2f}" if quote.low_price > 0 else EMPTY_DISPLAY
        tiles["ohlc"].set_value(
            open_text,
            subtitle=f"高 {high_text} · 低 {low_text}",
        )
        tiles["volume"].set_value(format_volume(quote.volume) if quote.volume > 0 else EMPTY_DISPLAY)
        tiles["amount"].set_value(format_amount(quote.amount) if quote.amount > 0 else EMPTY_DISPLAY)
        tiles["turnover"].set_value(f"{quote.turnover_rate:.2f}%" if quote.turnover_rate > 0 else EMPTY_DISPLAY)
        tiles["amplitude"].set_value(f"{quote.amplitude:.2f}%" if quote.amplitude > 0 else EMPTY_DISPLAY)
        tiles["time"].set_value(quote.trade_time or EMPTY_DISPLAY)

    def _show_scope_loading(self, scope: StockAnalysisScope) -> None:
        if scope == "overview":
            self._overview_panel.show_loading()
        elif scope == "short_term":
            self._short_term_tab.show_loading()
        elif scope == "sector":
            self._sector_tab.show_loading()
        elif scope == "concept":
            self._concept_tab.show_loading()
        elif scope == "capital":
            self._capital_tab.show_loading()
        elif scope == "events":
            self._events_tab.show_loading()
        elif scope == "holders":
            self._holders_tab.show_loading()
        elif scope == "financial":
            self._financial_tab.show_loading()

    def _start_load(
        self,
        *,
        scope: StockAnalysisScope,
        sync_financials: bool = False,
        force: bool = False,
    ) -> None:
        if self._closing:
            return
        if not force and scope in self._loaded_scopes:
            return
        if self._worker is not None and self._worker.isRunning():
            if scope not in self._pending_scopes and scope not in self._loaded_scopes:
                self._pending_scopes.append(scope)
            return

        stock_analysis = self._stock_analysis_service()
        if stock_analysis is None:
            self._status_label.setText("个股分析服务未就绪")
            return
        if scope in {"overview", "sector"} and self._analysis_service() is None:
            self._status_label.setText("分析服务未就绪")
            return
        if scope == "financial" and self._financial_service() is None:
            self._status_label.setText("财报服务未就绪")
            return

        self._loading_scope = scope
        if scope == "overview" and sync_financials:
            status = "正在加载概览并同步财报…"
        else:
            status = _SCOPE_STATUS.get(scope, "正在加载…")
        self._status_label.setText(status)
        set_panel_status_loading(self._status_label, True)
        self._refresh_btn.setEnabled(False)
        self._show_scope_loading(scope)

        worker = StockAnalysisWorker(
            vt_symbol=self._item.vt_symbol,
            scope=scope,
            stock_analysis_service=stock_analysis,
            quote_summary=self._quote_summary(),
            sync_financials=sync_financials,
            stock_name=self._quote.name if self._quote and self._quote.name else self._item.name,
            parent=self,
        )
        self._worker = worker
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _ensure_payload(self) -> StockAnalysisPayload:
        if self._payload is None:
            self._payload = StockAnalysisPayload(vt_symbol=self._item.vt_symbol)
        return self._payload

    def _merge_partial(self, partial: StockAnalysisPayload) -> StockAnalysisPayload:
        base = self._ensure_payload()
        scope = partial.scope
        if scope == "overview":
            base.technical = partial.technical
            base.relative_returns = partial.relative_returns
            base.overview_dashboard = partial.overview_dashboard
            if partial.financial_bundle is not None:
                base.financial_bundle = partial.financial_bundle
            if partial.financial_sync is not None:
                base.financial_sync = partial.financial_sync
        elif scope == "short_term":
            base.short_term = partial.short_term
        elif scope == "sector":
            base.sector = partial.sector
            base.valuation = partial.valuation
            base.valuation_history = partial.valuation_history
        elif scope == "concept":
            base.concept = partial.concept
        elif scope == "capital":
            base.moneyflow = partial.moneyflow
        elif scope == "events":
            base.events = partial.events
        elif scope == "holders":
            base.holders = partial.holders
        elif scope == "financial":
            base.financial_bundle = partial.financial_bundle
            base.financial_sync = partial.financial_sync
        if partial.warnings:
            base.warnings.extend(partial.warnings)
        return base

    def _apply_scope(self, scope: StockAnalysisScope) -> None:
        payload = self._ensure_payload()
        if scope == "overview":
            technical_text = format_technical_summary(
                payload.technical,
                relative_returns=payload.relative_returns,
            )
            self._overview_panel.show_payload(
                technical=payload.technical,
                technical_text=technical_text,
                relative_returns=payload.relative_returns,
                dashboard=payload.overview_dashboard,
            )
        elif scope == "short_term":
            self._short_term_tab.show_profile(payload.short_term)
        elif scope == "sector":
            self._sector_tab.show_profiles(
                payload.sector,
                payload.valuation,
                valuation_history=payload.valuation_history,
            )
        elif scope == "concept":
            self._concept_tab.show_profile(payload.concept)
        elif scope == "capital":
            self._capital_tab.show_profile(payload.moneyflow)
        elif scope == "events":
            self._events_tab.show_profile(payload.events)
        elif scope == "holders":
            self._holders_tab.show_profile(payload.holders)
        elif scope == "financial":
            sync_message = ""
            if payload.financial_sync is not None:
                sync_message = payload.financial_sync.message
            self._financial_tab.show_bundle(payload.financial_bundle, sync_message=sync_message)

    def _on_finished(self, payload_obj: object) -> None:
        if self._closing:
            return
        partial = payload_obj if isinstance(payload_obj, StockAnalysisPayload) else None
        self._worker = None
        self._loading_scope = None
        self._refresh_btn.setEnabled(True)
        set_panel_status_loading(self._status_label, False)

        if partial is None:
            self._status_label.setText("加载失败：无效 payload")
            self._run_pending_load()
            return

        self._merge_partial(partial)
        self._loaded_scopes.add(partial.scope)
        self._apply_scope(partial.scope)

        warnings = [item for item in partial.warnings if item]
        status = "加载完成"
        if partial.financial_sync is not None:
            status = partial.financial_sync.message or status
        if warnings:
            status += f" · {'；'.join(warnings[:2])}"
        self._status_label.setText(status)

        if self._tabs.currentIndex() == _TAB_CHART:
            self._ensure_chart_loaded()
        self._run_pending_load()

    def _run_pending_load(self) -> None:
        while self._pending_scopes:
            scope = self._pending_scopes.pop(0)
            if scope not in self._loaded_scopes:
                self._start_load(scope=scope, sync_financials=False)
                return

    def _on_failed(self, message: str) -> None:
        if self._closing:
            return
        failed_scope = self._loading_scope
        self._worker = None
        self._loading_scope = None
        self._refresh_btn.setEnabled(True)
        set_panel_status_loading(self._status_label, False)
        self._status_label.setText(message)
        page_notify(self, message, level="error")
        if failed_scope == "overview":
            self._overview_panel.show_payload(technical_text=message)
        self._run_pending_load()

    def _jump_from_overview(self, target: str) -> None:
        tab_index = _JUMP_TAB_INDEX.get(target)
        if tab_index is None:
            return
        self._tabs.setCurrentIndex(tab_index)
        if tab_index == _TAB_CHART:
            self._ensure_chart_loaded()
            return
        self._ensure_tab_data(tab_index)

    def _publish_ai_context(self) -> None:
        quote_service = get_quote_service(self._host.main_engine)
        if quote_service is None:
            return
        page = self._host.source_page.strip() or "分析"
        quote_service.publish_quote_context(
            page=f"个股分析·{page}",
            item=self._item,
            quote=self._quote,
        )

    def _build_ai_prompt(self) -> str:
        name = self._quote.name if self._quote and self._quote.name else self._item.name
        base = build_diagnose_ai_prompt(self._item.vt_symbol, name)
        if self._payload is not None:
            context = build_analysis_ai_context(self._payload)
            if context:
                base = f"{base}\n\n已知本地摘要：{context}"
        return base

    def _ask_ai(self) -> None:
        prompt = self._build_ai_prompt()
        scene = f"个股分析·{self._host.source_page or self._item.vt_symbol}"
        if self._ai_sidebar.show_and_ask(prompt, scene=scene):
            self._status_label.setText("已在右侧 AI 侧栏预填解读请求")
            return
        if self._host.event_engine is None:
            page_notify(self, "AI 服务未就绪", level="warning")
            return
        self._host.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(
                    prompt=prompt,
                    source_page=self._host.source_page,
                    use_full_page=True,
                ),
            )
        )
        self._status_label.setText("已在 AI 助手页打开解读")

    def _open_reports_center(self) -> None:

        parent = self.parent()
        focus_watchlist = None
        while parent is not None:
            if hasattr(parent, "focus_watchlist_symbol"):
                focus_watchlist = parent.focus_watchlist_symbol
                break
            parent = parent.parent()
        main_engine = self._host.main_engine
        if main_engine is None:
            return
        open_notes_reports_center(
            main_engine,
            self._host.event_engine,
            focus_watchlist=focus_watchlist,
            initial_vt_symbol=self._item.vt_symbol,
            parent=self,
        )
