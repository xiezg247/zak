"""AI 助手消息内标的链接的跳转与右键菜单。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ui.feedback import page_notify
from vnpy_llm.ui.panel.symbol_links import normalize_vt_symbol, parse_symbol_href

if TYPE_CHECKING:
    from vnpy_llm.ui.panel.chat import AiChatPanel


class AssistantSymbolActions:
    """解析 zak://symbol/ 链接并执行看盘/分析/回测等动作。"""

    def __init__(self, panel: AiChatPanel) -> None:
        self._panel = panel

    @property
    def _engine(self):
        return self._panel.engine

    def handle_link_click(self, url: QtCore.QUrl | str) -> bool:
        vt_symbol = parse_symbol_href(url.toString() if isinstance(url, QtCore.QUrl) else str(url))
        if vt_symbol is None:
            return False
        QtCore.QTimer.singleShot(0, lambda vt=vt_symbol: self.open_analysis(vt))
        return True

    def symbol_at(self, browser: QtWidgets.QTextBrowser, pos: QtCore.QPoint) -> str | None:
        anchor = browser.anchorAt(pos)
        if not anchor:
            return None
        return parse_symbol_href(anchor)

    def show_menu(
        self,
        parent: QtWidgets.QWidget,
        pos: QtCore.QPoint,
        vt_symbol: str,
        *,
        body: str = "",
    ) -> None:
        item = self._parse_item(vt_symbol)
        if item is None:
            page_notify(parent, f"无法解析标的：{vt_symbol}", level="warning")
            return
        menu = self._build_menu(item, body=body)
        menu.exec(parent.mapToGlobal(pos))

    def open_analysis(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_item(vt_symbol, name=name)
        if item is None:
            page_notify(self._panel, f"无法解析标的：{vt_symbol}", level="warning")
            return
        try:
            from vnpy_ashare.ui.features.stock_analysis import StockAnalysisHost, show_stock_analysis_vt_symbol
        except ImportError:
            page_notify(self._panel, "个股分析需要 vnpy-ashare 插件", level="warning")
            return
        host = StockAnalysisHost.from_main_engine(
            self._engine.main_engine,
            event_engine=self._engine.event_engine,
            source_page="AI 助手",
        )
        show_stock_analysis_vt_symbol(
            item.vt_symbol,
            host,
            name=item.name,
            parent=self._panel.window(),
            modality=QtCore.Qt.WindowModality.NonModal,
        )
        QtCore.QTimer.singleShot(0, self._panel._sync_all_bubble_widths)

    def focus_watchlist(self, vt_symbol: str) -> None:
        item = self._parse_item(vt_symbol)
        if item is None:
            return
        host = self._panel.window()
        if host is not None and hasattr(host, "focus_watchlist_symbol"):
            host.focus_watchlist_symbol(item.symbol, item.exchange.name)
            return
        page_notify(self._panel, "无法跳转到自选页", level="warning")

    def open_backtest(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_item(vt_symbol, name=name)
        if item is None:
            return
        try:
            from vnpy_ashare.app.events import EVENT_OPEN_BACKTEST, BacktestRequest
        except ImportError:
            page_notify(self._panel, "回测功能需要 vnpy-ashare 插件", level="warning")
            return
        self._engine.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(vt_symbol=item.vt_symbol, source_page="AI 助手", name=item.name),
            ),
        )

    def toggle_watchlist(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_item(vt_symbol, name=name)
        if item is None:
            return
        try:
            from vnpy_ashare.app.engine_access import get_watchlist_service
            from vnpy_ashare.storage.repositories.watchlist import watchlist_contains
        except ImportError:
            page_notify(self._panel, "自选功能需要 vnpy-ashare 插件", level="warning")
            return
        service = get_watchlist_service(self._engine.main_engine)
        if service is None:
            page_notify(self._panel, "自选服务未就绪", level="warning")
            return
        if watchlist_contains(item.symbol, item.exchange):
            if service.remove(item.symbol, item.exchange):
                page_notify(self._panel, f"已移出自选：{item.vt_symbol}", level="success")
            return
        reason = service.add_failure_reason(item.symbol, item.exchange)
        if reason == "duplicate":
            page_notify(self._panel, f"已在自选中：{item.vt_symbol}", level="info")
            return
        if reason == "full":
            page_notify(self._panel, "自选池已满", level="warning")
            return
        if service.add(item.symbol, item.exchange, item.name):
            page_notify(self._panel, f"已加入自选：{item.vt_symbol}", level="success")

    def open_reference_peer(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_item(vt_symbol, name=name)
        if item is None:
            return
        try:
            from vnpy_ashare.app.engine_access import get_watchlist_service
            from vnpy_ashare.ui.screener import show_reference_peer_dialog
        except ImportError:
            page_notify(self._panel, "找同类需要 vnpy-ashare 插件", level="warning")
            return
        service = get_watchlist_service(self._engine.main_engine)

        def watchlist_add(symbol: str, exchange, stock_name: str = "") -> bool:
            if service is None:
                return False
            return service.add(symbol, exchange, stock_name)

        show_reference_peer_dialog(
            vt_symbol=item.vt_symbol,
            reference_name=item.name,
            watchlist_add=watchlist_add if service is not None else None,
            parent=self._panel.window(),
        )

    def copy_vt_symbol(self, vt_symbol: str) -> None:
        vt = normalize_vt_symbol(vt_symbol) or vt_symbol
        QtGui.QGuiApplication.clipboard().setText(vt)
        page_notify(self._panel, f"已复制 {vt}", level="success")

    def fill_ai_prompt(self, prompt: str) -> None:
        self._panel.set_input_text(prompt)

    def _parse_item(self, vt_symbol: str, *, name: str = ""):
        try:
            from vnpy_ashare.ai.context.symbol import parse_stock_symbol
            from vnpy_ashare.domain.symbols import StockItem
        except ImportError:
            return None
        normalized = normalize_vt_symbol(vt_symbol) or vt_symbol
        item = parse_stock_symbol(normalized)
        if item is None:
            return None
        if name and not item.name:
            return StockItem(symbol=item.symbol, exchange=item.exchange, name=name)
        return item

    def _build_menu(self, item, *, body: str = "") -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self._panel)
        vt = item.vt_symbol
        title = item.name or vt

        analyze = menu.addAction("个股分析")
        analyze.triggered.connect(lambda: self.open_analysis(vt, name=item.name))

        focus = menu.addAction("在自选定位")
        focus.triggered.connect(lambda: self.focus_watchlist(vt))

        menu.addSeparator()

        try:
            from vnpy_ashare.storage.repositories.watchlist import watchlist_contains
        except ImportError:
            watchlist_contains = None  # type: ignore[assignment]

        if watchlist_contains is not None and watchlist_contains(item.symbol, item.exchange):
            watchlist_action = menu.addAction("移出自选")
        else:
            watchlist_action = menu.addAction("加入自选")
        watchlist_action.triggered.connect(lambda: self.toggle_watchlist(vt, name=item.name))

        backtest = menu.addAction("策略回测")
        backtest.triggered.connect(lambda: self.open_backtest(vt, name=item.name))

        peer = menu.addAction("找同类…")
        peer.triggered.connect(lambda: self.open_reference_peer(vt, name=item.name))

        menu.addSeparator()

        ai_menu = menu.addMenu("继续问 AI")
        self._populate_ai_submenu(ai_menu, item)

        menu.addSeparator()

        report = menu.addAction(f"存为分析报告（{title}）…")
        report.triggered.connect(lambda _checked=False, b=body: self._save_report(vt, item.name, body=b))

        journal = menu.addAction(f"追加到流水（{title}）")
        journal.triggered.connect(lambda _checked=False, b=body: self._save_journal(vt, item.name, body=b))

        copy_action = menu.addAction("复制 vt_symbol")
        copy_action.triggered.connect(lambda: self.copy_vt_symbol(vt))

        return menu

    def _populate_ai_submenu(self, menu: QtWidgets.QMenu, item) -> None:
        try:
            from vnpy_ashare.ai.context.quote.assembly import build_stock_completion_items
        except ImportError:
            disabled = menu.addAction("需要 vnpy-ashare 插件")
            disabled.setEnabled(False)
            return
        from vnpy_ashare.config import exchange_to_cn

        for entry in build_stock_completion_items(
            item.symbol,
            exchange_cn=exchange_to_cn(item.exchange),
            name=item.name,
        ):
            action = menu.addAction(entry.label)
            action.triggered.connect(lambda _checked=False, prompt=entry.prompt: self.fill_ai_prompt(prompt))

    def _context_stock(self, vt_symbol: str, name: str = ""):
        try:
            from vnpy_ashare.ui.features.notes_center.save_from_ai import ContextStock
        except ImportError:
            return None
        item = self._parse_item(vt_symbol, name=name)
        if item is None:
            return None
        return ContextStock(symbol=item.symbol, exchange=item.exchange.value, name=item.name)

    def _save_report(self, vt_symbol: str, name: str, *, body: str) -> None:
        stock = self._context_stock(vt_symbol, name)
        if stock is None:
            page_notify(self._panel, "无法解析标的", level="warning")
            return
        text = body.strip()
        if not text:
            page_notify(self._panel, "消息内容为空", level="info")
            return
        try:
            from vnpy_ashare.ui.features.notes_center.save_from_ai import save_message_as_report
        except ImportError:
            page_notify(self._panel, "笔记功能需要 vnpy-ashare 插件", level="warning")
            return
        if save_message_as_report(self._engine.main_engine, text, parent=self._panel, stock=stock):
            page_notify(self._panel, f"已保存分析报告（{stock.vt_symbol}）", level="success")

    def _save_journal(self, vt_symbol: str, name: str, *, body: str) -> None:
        stock = self._context_stock(vt_symbol, name)
        if stock is None:
            page_notify(self._panel, "无法解析标的", level="warning")
            return
        text = body.strip()
        if not text:
            page_notify(self._panel, "消息内容为空", level="info")
            return
        try:
            from vnpy_ashare.ui.features.notes_center.save_from_ai import save_message_as_journal
        except ImportError:
            page_notify(self._panel, "笔记功能需要 vnpy-ashare 插件", level="warning")
            return
        if save_message_as_journal(self._engine.main_engine, text, stock=stock):
            page_notify(self._panel, f"已追加流水（{stock.vt_symbol}）", level="success")
        else:
            page_notify(self._panel, "保存失败或内容被截断为空", level="warning")
