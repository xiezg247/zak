"""个股分析对话框。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context import build_diagnose_ai_prompt
from vnpy_ashare.app.engine_access import get_analysis_service, get_financial_service
from vnpy_ashare.app.events import EVENT_ASK_AI, EVENT_OPEN_BACKTEST, AskAiRequest, BacktestRequest
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.ui.quotes.panels.diagnose import format_diagnose_html
from vnpy_ashare.ui.quotes.stock_analysis.chart_tab import StockAnalysisChartTab
from vnpy_ashare.ui.quotes.stock_analysis.financial_tab import FinancialAnalysisTab
from vnpy_ashare.ui.quotes.stock_analysis.host import StockAnalysisHost
from vnpy_ashare.ui.quotes.stock_analysis.sector_tab import SectorAnalysisTab
from vnpy_ashare.ui.quotes.workers.stock_analysis_worker import StockAnalysisPayload, StockAnalysisWorker
from vnpy_common.ui.dialog_shell import (
    apply_standard_dialog_layout,
    build_panel_footer,
    set_panel_status_loading,
    setup_responsive_dialog,
)
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.loading_overlay import LoadingContentHost
from vnpy_common.ui.panel_widgets import MetricTile, content_card, panel_status_label, section_title, tab_page
from vnpy_common.ui.qt_helpers import release_thread
from vnpy_common.ui.scroll_area import frameless_scroll_area
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_panel import build_stock_analysis_stylesheet
from vnpy_common.ui.theme.html_format import format_loading_html
from vnpy_common.ui.theme.market_colors import pct_change_color

_TAB_OVERVIEW = 0
_TAB_QUOTE = 1
_TAB_CHART = 2
_TAB_SECTOR = 3
_TAB_FINANCIAL = 4


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

        meta = _quote_header_meta(quote, item)
        self.setWindowTitle(f"个股分析 · {meta['name']}")
        setup_responsive_dialog(self, parent)

        header = self._build_header(meta)
        self._status_label = panel_status_label("正在加载…")
        tabs = self._build_tabs()
        self._content_host = LoadingContentHost(tabs)
        footer = self._build_footer()

        apply_standard_dialog_layout(
            self,
            header=header,
            content=self._content_host,
            footer=footer,
        )

        theme_manager().bind_stylesheet(self, extra=build_stock_analysis_stylesheet)
        self._render_quote_tab()
        self._set_loading(True)
        self._start_load(force_financial=False)

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
            change_label.setStyleSheet(
                f"color: {meta['change_color']}; background-color: {meta['change_bg']};"
            )
        right.addWidget(price_label)
        if meta["change"]:
            right.addWidget(change_label)

        row.addLayout(left, stretch=1)
        row.addLayout(right)
        return header

    def _build_tabs(self) -> QtWidgets.QTabWidget:
        self._overview_body = QtWidgets.QLabel("加载中…")
        self._overview_body.setWordWrap(True)
        self._overview_body.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._overview_body.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self._overview_body.setObjectName("DiagnoseBody")

        self._technical_body = QtWidgets.QLabel("")
        self._technical_body.setWordWrap(True)
        self._technical_body.setObjectName("DiagnoseBody")
        self._technical_body.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)

        overview_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        overview_split.setChildrenCollapsible(False)
        overview_split.addWidget(
            content_card(
                section_title("综合诊断"),
                frameless_scroll_area(self._overview_body),
            )
        )
        overview_split.addWidget(
            content_card(
                section_title("本地技术面"),
                self._technical_body,
            )
        )
        overview_split.setStretchFactor(0, 3)
        overview_split.setStretchFactor(1, 2)

        self._quote_page = self._build_quote_page()
        self._chart_tab = StockAnalysisChartTab()
        self._chart_tab.set_retired_workers(self._host.retired_workers)
        self._sector_tab = SectorAnalysisTab()
        self._financial_tab = FinancialAnalysisTab()

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("DocumentTabWidget")
        tabs.setDocumentMode(True)
        tabs.addTab(tab_page(overview_split), "概览")
        tabs.addTab(self._quote_page, "行情")
        tabs.addTab(tab_page(self._chart_tab, margins=(0, 4, 0, 0)), "图表")
        tabs.addTab(self._sector_tab, "板块")
        tabs.addTab(self._financial_tab, "财务")
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs
        return tabs

    def _build_quote_page(self) -> QtWidgets.QWidget:
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
            ("volume", 1, 0),
            ("amount", 1, 1),
            ("turnover", 1, 2),
            ("amplitude", 2, 0),
            ("time", 2, 1),
        ]
        for key, row, col in positions:
            grid.addWidget(self._quote_tiles[key], row, col)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        wrapper = QtWidgets.QWidget()
        wrapper.setLayout(grid)
        return tab_page(content_card(wrapper, margins=(8, 8, 8, 8)))

    def _build_footer(self) -> QtWidgets.QWidget:
        self._refresh_btn = QtWidgets.QPushButton("刷新")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.clicked.connect(lambda: self._start_load(force_financial=True))
        self._ai_btn = QtWidgets.QPushButton("问 AI 解读")
        self._ai_btn.setObjectName("ActionButton")
        self._ai_btn.clicked.connect(self._ask_ai)
        self._backtest_btn = QtWidgets.QPushButton("策略回测")
        self._backtest_btn.setObjectName("SecondaryButton")
        self._backtest_btn.clicked.connect(self._open_backtest)
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.close)
        return build_panel_footer(
            self._status_label,
            self._refresh_btn,
            self._ai_btn,
            self._backtest_btn,
            close_btn,
        )

    def _set_loading(self, loading: bool, *, title: str = "正在加载个股分析…") -> None:
        hint = "综合诊断 · 财报 · 板块估值"
        if loading:
            self._content_host.show_loading(title, hint=hint)
            self._status_label.setText(title)
            set_panel_status_loading(self._status_label, True)
            self._overview_body.setText(
                format_loading_html(title, hint="正在拉取问小达诊断与本地技术面")
            )
            self._technical_body.setText("正在分析本地技术面…")
            self._sector_tab.show_loading()
            self._financial_tab.show_loading()
        else:
            self._content_host.hide_loading()
            set_panel_status_loading(self._status_label, False)

    def closeEvent(self, event) -> None:
        self._closing = True
        self._chart_tab.shutdown()
        if self._worker is not None:
            release_thread(self._host.retired_workers, self._worker, timeout_ms=1500)
            self._worker = None
        super().closeEvent(event)

    def _on_tab_changed(self, index: int) -> None:
        if index == _TAB_CHART:
            self._ensure_chart_loaded()

    def _ensure_chart_loaded(self) -> None:
        if self._chart_loaded or self._closing:
            return
        self._chart_loaded = True
        self._chart_tab.load(self._item, quote=self._quote)

    def _analysis_service(self):
        return get_analysis_service(self._host.main_engine)

    def _financial_service(self):
        return get_financial_service(self._host.main_engine)

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

    def _render_quote_tab(self) -> None:
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
        tiles["ohlc"].set_value(
            f"{quote.open_price:.2f}",
            subtitle=f"高 {quote.high_price:.2f} · 低 {quote.low_price:.2f}",
        )
        tiles["volume"].set_value(f"{quote.volume:,.0f}")
        tiles["amount"].set_value(f"{quote.amount:,.0f}")
        tiles["turnover"].set_value(f"{quote.turnover_rate:.2f}%")
        tiles["amplitude"].set_value(f"{quote.amplitude:.2f}%")
        tiles["time"].set_value(quote.trade_time or "—")

    def _start_load(self, *, force_financial: bool) -> None:
        if self._closing:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        analysis = self._analysis_service()
        financial = self._financial_service()
        if analysis is None and financial is None:
            self._set_loading(False)
            self._status_label.setText("分析服务未就绪")
            return

        self._status_label.setText("正在加载…")
        self._refresh_btn.setEnabled(False)
        self._set_loading(True, title="正在加载个股分析…")
        worker = StockAnalysisWorker(
            vt_symbol=self._item.vt_symbol,
            analysis_service=analysis,
            financial_service=financial,
            quote_summary=self._quote_summary(),
            sync_financials=force_financial or self._payload is None,
            stock_name=self._quote.name if self._quote and self._quote.name else self._item.name,
            parent=self,
        )
        self._worker = worker
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _on_finished(self, payload_obj: object) -> None:
        if self._closing:
            return
        self._worker = None
        self._refresh_btn.setEnabled(True)
        payload = payload_obj if isinstance(payload_obj, StockAnalysisPayload) else None
        if payload is None:
            self._set_loading(False)
            self._status_label.setText("加载失败：无效 payload")
            return
        self._payload = payload
        self._set_loading(False)
        self._overview_body.setText(format_diagnose_html(payload.diagnose))
        self._technical_body.setText(self._format_technical(payload.technical))
        sync_message = ""
        if payload.financial_sync is not None:
            sync_message = payload.financial_sync.message
        self._financial_tab.show_bundle(payload.financial_bundle, sync_message=sync_message)
        self._sector_tab.show_profiles(payload.sector, payload.valuation)
        warnings = payload.warnings
        status = sync_message or "加载完成"
        if warnings:
            status += f" · {'；'.join(warnings[:2])}"
        self._status_label.setText(status)
        if self._tabs.currentIndex() == _TAB_CHART:
            self._ensure_chart_loaded()

    def _on_failed(self, message: str) -> None:
        if self._closing:
            return
        self._worker = None
        self._refresh_btn.setEnabled(True)
        self._set_loading(False)
        self._status_label.setText(message)
        page_notify(self, message, level="error")

    @staticmethod
    def _format_technical(data: dict[str, Any]) -> str:
        if not data:
            return "暂无本地技术面"
        if data.get("error"):
            return str(data["error"])
        warnings = data.get("warnings") or []
        if warnings:
            return "；".join(str(item) for item in warnings)
        ma = data.get("ma") or {}
        ret = (data.get("period_return") or {}).get("return_pct")
        ret_text = f"{ret:+.2f}%" if isinstance(ret, (int, float)) else "—"
        lines = [
            f"截至 {data.get('as_of', '—')} · 收盘 {data.get('last_close', '—')}",
            f"MA5 / MA10 / MA20 / MA60",
            f"{ma.get('ma5', '—')} / {ma.get('ma10', '—')} / {ma.get('ma20', '—')} / {ma.get('ma60', '—')}",
            f"均线排列：{data.get('ma_alignment', '—')}",
            f"5日量比 {data.get('volume_ratio_5d', '—')} · 区间涨跌 {ret_text}",
        ]
        return "\n".join(lines)

    def _ask_ai(self) -> None:
        if self._host.event_engine is None:
            return
        name = self._quote.name if self._quote and self._quote.name else self._item.name
        self._host.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(
                    prompt=build_diagnose_ai_prompt(self._item.vt_symbol, name),
                    source_page=self._host.source_page,
                ),
            )
        )

    def _open_backtest(self) -> None:
        if self._host.event_engine is None:
            return
        name = self._quote.name if self._quote and self._quote.name else self._item.name
        self._host.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(
                    vt_symbol=self._item.vt_symbol,
                    source_page=self._host.source_page,
                    name=name,
                ),
            )
        )
