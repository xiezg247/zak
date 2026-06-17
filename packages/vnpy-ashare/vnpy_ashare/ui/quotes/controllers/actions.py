"""看盘页用户操作：诊断、AI 问句、回测、右键菜单与行情刷新。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context import (
    build_diagnose_ai_prompt,
    build_historical_ai_prompt,
    build_positions_ai_prompt,
    build_signal_panel_ai_prompt,
    build_signal_panel_batch_ai_prompt,
    build_team_analysis_ai_prompt,
    build_technical_ai_prompt,
)
from vnpy_ashare.app.events import EVENT_ASK_AI, EVENT_OPEN_BACKTEST, AskAiRequest, BacktestRequest
from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.data.bar_health import BarHealthStatus, list_status
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.domain.market.depth_snapshot import DepthSnapshot
from vnpy_ashare.quotes.core.enrich import merge_quote_maps_into
from vnpy_ashare.quotes.format import format_volume
from vnpy_ashare.services.signals.runtime import format_signal_context_extra
from vnpy_ashare.trading.journal.discipline_context import format_trading_discipline_extra
from vnpy_ashare.ui.features.stock_analysis import show_stock_analysis_from_quotes_page
from vnpy_ashare.ui.quotes.chart.tab_indices import DAILY_TAB_INDEX, MINUTE_TAB_INDEX
from vnpy_ashare.ui.quotes.page.config import AI_CONTEXT_DEBOUNCE_MS
from vnpy_ashare.ui.quotes.workers import DepthRefreshWorker, DiagnoseWorker, QuotesRefreshWorker
from vnpy_ashare.ui.screener import show_reference_peer_dialog
from vnpy_ashare.ui.styles import NAV_MUTED_COLOR
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors, quote_change_color

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class ActionsController:
    """QuotesPage 工具栏动作、右键菜单与报价头刷新。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._ai_context_timer = QtCore.QTimer(page)
        self._ai_context_timer.setSingleShot(True)
        self._ai_context_timer.setInterval(AI_CONTEXT_DEBOUNCE_MS)
        self._ai_context_timer.timeout.connect(self._publish_ai_context)

    @property
    def _p(self) -> QuotesPage:
        return self._page

    def update_action_buttons(self) -> None:
        page = self._p
        item = page.current_item
        if page.config.show_download_button:
            if page.config.show_chart_tabs:
                on_download_tab = page.chart_panel is not None and page.chart_panel.current_tab_index() in (DAILY_TAB_INDEX, MINUTE_TAB_INDEX)
                page.download_button.setVisible(on_download_tab)
                page.download_button.setEnabled(item is not None and on_download_tab)
            else:
                page.download_button.setEnabled(item is not None)
        if page.config.show_fill_button:
            if item is None:
                page.fill_button.setEnabled(False)
            else:
                key = (item.symbol, item.exchange)
                status = page.bar_list_status.get(key, list_status(page.bar_meta.get(key)))
                page.fill_button.setEnabled(status in (BarHealthStatus.STALE, BarHealthStatus.GAPS))
        if page.config.show_redownload_button:
            if item is None:
                page.redownload_button.setEnabled(False)
            else:
                key = (item.symbol, item.exchange)
                page.redownload_button.setEnabled(key in page.bar_meta)
        if page.config.show_delete_button:
            button = getattr(page, "delete_local_button", None)
            if button is not None:
                if item is None:
                    button.setEnabled(False)
                else:
                    key = (item.symbol, item.exchange)
                    button.setEnabled(key in page.bar_meta)
        if page.config.show_add_watchlist_button or page.config.show_remove_watchlist_button or page.config.show_watchlist_move_buttons:
            page._watchlist.update_action_buttons(item)
        if page.config.show_backtest_button:
            page.backtest_button.setEnabled(item is not None)
        if page.config.show_batch_backtest_button:
            page._batch_backtest.update_action_buttons()
        if page.config.show_batch_fill_button or page.config.show_batch_gap_fill_button:
            page._local.update_batch_toolbar_buttons()
        if page.config.show_diagnose_button:
            page.diagnose_button.setEnabled(item is not None)
        if page.config.show_stock_notes:
            page.quick_note_button.setEnabled(item is not None)

    def on_chart_tab_changed(self, index: int) -> None:
        page = self._p
        if page.config.show_download_button and page.config.show_chart_tabs:
            show = index in (DAILY_TAB_INDEX, MINUTE_TAB_INDEX)
            page.download_button.setVisible(show)
            if index == MINUTE_TAB_INDEX:
                page.download_button.setText("下载分K到本地")
            else:
                page.download_button.setText("下载日K到本地")
        self.update_action_buttons()

    def schedule_ai_context(self) -> None:
        """WebSocket 高频推送时合并 AI 上下文写入。"""
        self._ai_context_timer.start()

    def emit_ai_context(self) -> None:
        """选中变更等须立即同步的场景。"""
        self._ai_context_timer.stop()
        self._publish_ai_context()

    def _publish_ai_context(self) -> None:
        """看盘页选中/行情变更 → QuoteService → context_store → AI 面板监听刷新。"""
        page = self._p
        quote = None
        bar_count = 0
        if page.current_item is not None:
            quote = page.quote_map.get(page.current_item.tickflow_symbol)
            key = (page.current_item.symbol, page.current_item.exchange)
            meta = page.bar_meta.get(key)
            bar_count = meta.count if meta else 0

        quote_service = page._get_quote_service()
        if quote_service is None:
            return
        quote_service.publish_quote_context(
            page=page.page_name,
            item=page.current_item,
            quote=quote,
            bar_count=bar_count,
            signal_extra=self._context_extra(),
        )

    def _context_extra(self) -> str:
        parts: list[str] = []
        multiview = self._multiview_context_extra()
        if multiview:
            parts.append(multiview)
        signal = self._signal_context_extra()
        if signal:
            parts.append(signal)
        note = self._note_context_extra()
        if note:
            parts.append(note)
        discipline = self._trading_discipline_context_extra()
        if discipline:
            parts.append(discipline)
        return "\n\n".join(parts)

    def _trading_discipline_context_extra(self) -> str:
        page = self._p
        if page.page_name != "自选" or not page.config.show_watchlist_positions:
            return ""

        vt_symbol = page.current_item.vt_symbol if page.current_item is not None else None
        return format_trading_discipline_extra(
            position_cache=page.position_cache,
            vt_symbol=vt_symbol,
        )

    def _multiview_context_extra(self) -> str:
        page = self._p
        if page.page_name != "自选" or not page.config.show_watchlist_multiview:
            return ""
        if not page._multiview.is_multiview_active():
            return ""
        return page._multiview.board_summary_text()

    def _note_context_extra(self) -> str:
        page = self._p
        if not page.config.show_stock_notes:
            return ""
        item = page.current_item
        if item is None:
            return ""
        service = page._get_note_service()
        if service is None:
            return ""
        bundle = service.get_bundle(item.symbol, item.exchange)
        return service.build_ai_snippet(bundle)

    def _signal_context_extra(self) -> str:
        page = self._p
        if page.page_name != "自选" or not page.config.show_watchlist_signals:
            return ""
        item = page.current_item
        if item is None:
            return ""
        panel = getattr(page, "signal_panel", None)
        if panel is None or not panel.enabled:
            return ""
        if item.vt_symbol not in panel.symbols:
            return ""
        snap = page.signal_cache.get(item.vt_symbol)
        if snap is None:
            return ""
        quote = page.quote_map.get(item.tickflow_symbol)
        cfg = page.signal_config.normalized()
        return format_signal_context_extra(
            snap,
            quote=quote,
            fast_window=cfg.fast_window,
            slow_window=cfg.slow_window,
        )

    def update_quote_header(self, item: StockItem) -> None:
        page = self._p
        quote = page.quote_map.get(item.tickflow_symbol)
        page.quote_name_label.setText(quote.name if quote and quote.name else item.name)
        page.quote_code_label.setText(f"  {format_vt_symbol_cn(item.symbol, item.exchange)}")

        if not quote:
            page.quote_price_label.setText("—")
            page.quote_change_label.setText("")
            return

        colors = market_colors(theme_manager().tokens())
        color = quote_change_color(quote, theme_manager().tokens())
        page.quote_price_label.setText(f"{quote.last_price:.2f}")
        page.quote_price_label.setStyleSheet(f"color: {color};")
        page.quote_change_label.setText(f"  {quote.change_amount:+.2f}  ({quote.change_pct:+.2f}%)")
        page.quote_change_label.setStyleSheet(f"color: {color}; font-size: 14px;")

        if page._open_label is not None and page._high_label is not None and page._low_label is not None and page._volume_label is not None:
            open_text = f"今开 {quote.open_price:.2f}" if quote.open_price else "今开 —"
            page._open_label.setText(open_text)
            page._high_label.setText(f"最高 {quote.high_price:.2f}" if quote.high_price else "最高 —")
            page._high_label.setStyleSheet(f"color: {colors.rise}; font-size: 12px;")
            page._low_label.setText(f"最低 {quote.low_price:.2f}" if quote.low_price else "最低 —")
            page._low_label.setStyleSheet(f"color: {colors.fall}; font-size: 12px;")
            vol_text = format_volume(quote.volume) if quote.volume else "—"
            page._volume_label.setText(f"量 {vol_text}")
            page._volume_label.setStyleSheet(f"color: {NAV_MUTED_COLOR}; font-size: 12px;")

    def refresh_charts_only(self) -> None:
        page = self._p
        current = page.current_item
        chart_section = getattr(page, "chart_section", None)
        if chart_section is not None and not chart_section.is_expanded():
            return
        if current is None or page.chart_panel is None or not page.config.show_kline:
            return
        page.chart_panel.update_quote(page.quote_map.get(current.tickflow_symbol))
        page.chart_panel.refresh_active()

    def refresh_depth(self) -> None:
        page = self._p
        if not page._active or not page.config.show_depth_panel or page.depth_panel is None:
            return
        if page._use_quote_stream():
            return
        if page._depth_permission_denied or not page.current_item:
            return
        if page._thread_active(page._depth_worker):
            return

        page._depth_generation += 1
        generation = page._depth_generation
        item = page.current_item
        target_key = (item.symbol, item.exchange)

        worker = DepthRefreshWorker(item)
        page._depth_worker = worker
        depth_panel = page.depth_panel

        def on_finished(depth: object) -> None:
            if page._depth_worker is worker:
                page._depth_worker = None
            try:
                if generation != page._depth_generation:
                    return
                if not page._active or page.current_item is None:
                    return
                if (page.current_item.symbol, page.current_item.exchange) != target_key:
                    return
                if isinstance(depth, DepthSnapshot) and depth_panel is not None:
                    depth_panel.update_depth(depth)
            finally:
                page._release_worker(worker)

        def on_permission_denied(_message: str) -> None:
            if page._depth_worker is worker:
                page._depth_worker = None
            try:
                if generation != page._depth_generation:
                    return
                page._depth_permission_denied = True
                if depth_panel is not None:
                    depth_panel.show_permission_denied("未开通市场深度权限")
            finally:
                page._release_worker(worker)

        def on_failed(_msg: str) -> None:
            if page._depth_worker is worker:
                page._depth_worker = None
            page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.permission_denied.connect(on_permission_denied)
        worker.failed.connect(on_failed)
        worker.start()

    def refresh_quotes(self) -> None:
        page = self._p
        if not page._active or not page.config.quote_source:
            return
        if page.quote_auto_refresh_enabled() and not is_ashare_trading_session():
            page.schedule_quote_auto_refresh()
            return
        if page.config.use_market_rank:
            if not page.market_auto_refresh_enabled():
                return
            if page.config.market_scroll_paging and page._market_quote_refresh_paused():
                return
            self.refresh_quotes_rest()
            return
        if not page.display_stocks:
            page.schedule_quote_auto_refresh()
            return
        if page._use_quote_stream():
            self.refresh_charts_only()
            page.schedule_quote_auto_refresh()
            return
        self.refresh_quotes_rest()

    def refresh_quotes_manual(self) -> None:
        """用户手动刷新行情：绕过 WebSocket 流，强制 REST 拉取当前列表报价。"""
        page = self._p
        if not page.config.quote_source:
            return
        if not page.display_stocks:
            page._toast.info("列表为空，无可刷新标的")
            return
        if page._thread_active(page._quotes_worker):
            page._toast.info("行情刷新进行中，请稍候")
            return
        self.refresh_quotes_rest()

    def refresh_quotes_rest(self) -> None:
        page = self._p
        if not page.display_stocks:
            return
        if page._thread_active(page._quotes_worker):
            return
        if page.config.market_scroll_paging and page._market_quote_refresh_paused():
            return

        if page.config.show_depth_panel:
            self.refresh_depth()

        refresh_source = page.config.quote_refresh_source or page.config.quote_source or "watchlist"
        if page.config.use_market_rank and page.config.market_full_list and page._market_catalog_loaded and page.market_auto_refresh_enabled():
            refresh_items = list(page._market_catalog)
        elif page.config.market_scroll_paging:
            refresh_items = page._table.visible_market_items()
        else:
            refresh_items = list(page.display_stocks)
        if not refresh_items:
            return
        worker = QuotesRefreshWorker(refresh_items, refresh_source)
        page._quotes_worker = worker
        current = page.current_item

        def on_finished(quotes: dict) -> None:
            if page._quotes_worker is worker:
                page._quotes_worker = None
            try:
                if not page._active:
                    return

                merge_quote_maps_into(page.quote_map, quotes)
                if page.config.market_full_list and page._market_catalog_loaded:
                    merge_quote_maps_into(page._market_catalog_quotes, quotes)
                if page.config.use_market_rank and page.config.market_full_list and page._market_catalog_loaded:
                    page._table.apply_market_display()
                elif page.config.market_scroll_paging:
                    page._table.refresh_visible_table_quotes()
                else:
                    page._refresh_table_quotes()
                page._update_quote_source_label()
                if current:
                    self.update_quote_header(current)
                    if page.chart_panel is not None:
                        page.chart_panel.update_quote(quotes.get(current.tickflow_symbol))
                        page.chart_panel.refresh_active()
                if page.quote_auto_refresh_enabled():
                    page.schedule_quote_auto_refresh()
            finally:
                page._release_worker(worker)

        def on_failed(_msg: str) -> None:
            if page._quotes_worker is worker:
                page._quotes_worker = None
            try:
                if page.quote_auto_refresh_enabled():
                    page.schedule_quote_auto_refresh()
            finally:
                page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def run_diagnose_for_selected(self) -> None:
        page = self._p
        if not page.current_item:
            return
        if not page.config.show_diagnose_panel:
            self.ask_ai_for_diagnose()
            return
        if page._thread_active(page._diagnose_worker):
            return
        service = page._get_analysis_service()
        if service is None:
            page._toast.warning("分析服务未就绪")
            return

        vt_symbol = page.current_item.vt_symbol
        if page.diagnose_panel is not None:
            page.diagnose_panel.show_loading(vt_symbol)

        worker = DiagnoseWorker(service, vt_symbol=vt_symbol, parent=page)
        page._diagnose_worker = worker
        worker.finished.connect(self.on_diagnose_finished)
        worker.failed.connect(self.on_diagnose_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _ask_ai(self, prompt: str) -> None:
        page = self._p
        if page.current_item is None or page.event_engine is None:
            return
        self.emit_ai_context()
        page.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(
                    prompt=prompt,
                    source_page=page.page_name,
                ),
            )
        )

    def _item_title(self) -> str | None:
        page = self._p
        item = page.current_item
        if item is None:
            return None
        quote = page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        return f"{name}（{item.vt_symbol}）" if name else item.vt_symbol

    def ask_ai_for_diagnose(self) -> None:
        page = self._p
        item = page.current_item
        if item is None or page.event_engine is None:
            return
        quote = page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        self._ask_ai(build_diagnose_ai_prompt(item.vt_symbol, name))

    def ask_ai_for_team_analysis(self) -> None:
        page = self._p
        item = page.current_item
        if item is None or page.event_engine is None:
            return
        quote = page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        self._ask_ai(build_team_analysis_ai_prompt(item.vt_symbol, name))

    def ask_ai_for_technical(self) -> None:
        title = self._item_title()
        if title is None:
            return
        item = self._p.current_item
        assert item is not None
        quote = self._p.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        self._ask_ai(build_technical_ai_prompt(item.vt_symbol, name))

    def ask_ai_for_positions(self) -> None:
        page = self._p
        item = page.current_item
        if item is None:
            return
        quote = page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        cfg = page.position_config.normalized().effective_signal_config(page.signal_config)
        snap = page.position_cache.get(item.vt_symbol)

        discipline = format_trading_discipline_extra(
            position_cache=page.position_cache,
            vt_symbol=item.vt_symbol,
        )
        self._ask_ai(
            build_positions_ai_prompt(
                item.vt_symbol,
                name,
                class_name=cfg.class_name,
                fast_window=cfg.fast_window,
                slow_window=cfg.slow_window,
                cost_price=snap.cost_price if snap is not None else None,
                volume=snap.volume if snap is not None else None,
                unrealized_pnl_pct=snap.unrealized_pnl_pct if snap is not None else None,
                t1_locked=snap.t1_locked if snap is not None else None,
                discipline_extra=discipline,
            )
        )

    def ask_ai_for_signals(self) -> None:
        page = self._p
        item = page.current_item
        if item is None:
            return
        self._ask_ai_for_signal_symbol(item.vt_symbol)

    def ask_ai_for_signal_panel_batch(self) -> None:
        """信号区「AI 扫区」：批量解读名单内全部标的。"""
        page = self._p
        panel = getattr(page, "signal_panel", None)
        if panel is None or not panel.enabled:
            page._toast.warning("请先启用策略信号区")
            return
        if not panel.symbols:
            page._toast.warning("信号区暂无监控标的")
            return
        cfg = page.signal_config.normalized()
        self._ask_ai(
            build_signal_panel_batch_ai_prompt(
                class_name=cfg.class_name,
                fast_window=cfg.fast_window,
                slow_window=cfg.slow_window,
                symbol_count=len(panel.symbols),
            )
        )

    def ask_ai_for_signal_panel(self, vt_symbol: str | None = None) -> None:
        """信号区「AI 解读」：优先选中行，否则主表当前行（须在信号区名单内）。"""
        page = self._p
        panel = getattr(page, "signal_panel", None)
        if panel is None or not panel.enabled:
            page._toast.warning("请先启用策略信号区")
            return

        target = (vt_symbol or "").strip()
        if not target:
            selected = panel.selected_vt_symbols()
            if len(selected) == 1:
                target = selected[0]
            elif len(selected) > 1:
                page._toast.warning("AI 解读一次仅支持单只标的")
                return
            elif page.current_item is not None and page.current_item.vt_symbol in panel.symbols:
                target = page.current_item.vt_symbol
        if not target:
            page._toast.warning("请先在策略信号区选择标的")
            return
        if target not in panel.symbols:
            page._toast.warning("该标的不在策略信号区名单内")
            return

        item = page.find_stock_item(target)
        if item is None:
            return
        if page.current_item is None or page.current_item.vt_symbol != target:
            page._select_stock_key((item.symbol, item.exchange))
        # 延后跳转 AI 页，避免同步触发 K 线加载后立即 deactivate 导致 QThread 竞态。
        QtCore.QTimer.singleShot(0, lambda vt=target: self._ask_ai_for_signal_symbol(vt))

    def _ask_ai_for_signal_symbol(self, vt_symbol: str) -> None:
        page = self._p
        item = page.find_stock_item(vt_symbol)
        if item is None:
            return
        quote = page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        fast_window = 10
        slow_window = 20
        class_name = "AshareDoubleMaStrategy"
        context_extra = ""
        if page.config.show_watchlist_signals and page.page_name == "自选":
            cfg = page.signal_config.normalized()
            fast_window = cfg.fast_window
            slow_window = cfg.slow_window
            class_name = cfg.class_name
            snap = page.signal_cache.get(vt_symbol)
            if snap is not None:
                context_extra = format_signal_context_extra(
                    snap,
                    quote=quote,
                    fast_window=fast_window,
                    slow_window=slow_window,
                )
        self._ask_ai(
            build_signal_panel_ai_prompt(
                vt_symbol,
                name,
                class_name=class_name,
                fast_window=fast_window,
                slow_window=slow_window,
                context_extra=context_extra,
            )
        )

    def ask_ai_for_trend(self) -> None:
        if self._item_title() is None:
            return
        item = self._p.current_item
        assert item is not None
        quote = self._p.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        self._ask_ai(build_historical_ai_prompt(item.vt_symbol, name, lookback=20))

    def on_diagnose_finished(self, payload: dict) -> None:
        page = self._p
        page._diagnose_worker = None
        if page.diagnose_panel is not None:
            page.diagnose_panel.show_result(payload)
        # 诊断结果经 AnalysisService 写入 context_store，再刷新看盘 AI 上下文
        analysis = page._get_analysis_service()
        if analysis is not None:
            analysis.set_diagnose_result(payload)
        self.emit_ai_context()

    def on_diagnose_failed(self, message: str) -> None:
        page = self._p
        page._diagnose_worker = None
        if page.diagnose_panel is not None:
            page.diagnose_panel.show_result({"error": message})
        page.status_label.setText(message)

    def open_backtest_for_selected(self) -> None:
        page = self._p
        if not page.current_item or page.event_engine is None:
            return
        item = page.current_item
        quote = page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        page.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(
                    vt_symbol=item.vt_symbol,
                    source_page=page.page_name,
                    name=name,
                ),
            )
        )

    def show_context_menu(
        self,
        pos: QtCore.QPoint,
        *,
        item: StockItem | None = None,
        global_pos: QtCore.QPoint | None = None,
    ) -> None:
        page = self._p
        if item is None:
            row = page.market_table.indexAt(pos).row()
            if row < 0:
                return
            model_index = page.market_table.model().index(row, 0)
            selection = page.market_table.selectionModel()
            if selection is None or not selection.isSelected(model_index):
                page.market_table.selectRow(row)
            item = page._stock_at_row(row)
            if item is None:
                return
        menu = self._build_stock_context_menu(item)
        popup_at = global_pos if global_pos is not None else page.market_table.viewport().mapToGlobal(pos)
        menu.popup(popup_at)

    def _build_stock_context_menu(self, item: StockItem) -> QtWidgets.QMenu:
        page = self._p
        menu = QtWidgets.QMenu(page)

        action = menu.addAction("个股分析")
        action.triggered.connect(lambda _checked=False, it=item: self.open_stock_analysis(it))
        if page.config.show_stock_notes and hasattr(page, "stock_note_panel"):
            action = menu.addAction("添加笔记")
            action.triggered.connect(page.quick_note_for_selected)
        menu.addSeparator()

        ai_menu = menu.addMenu("AI 分析 ▸")
        ai_menu.addAction("综合诊断", self.ask_ai_for_diagnose)
        ai_menu.addAction("团队全面分析", self.ask_ai_for_team_analysis)
        ai_menu.addAction("技术形态", self.ask_ai_for_technical)
        ai_menu.addAction("双均线信号", self.ask_ai_for_signals)
        if page.page_name == "自选" and page.config.show_watchlist_positions:
            position_service = page._get_position_service()
            if position_service is not None and position_service.contains(item.symbol, item.exchange):
                ai_menu.addAction("持仓策略", self.ask_ai_for_positions)
        ai_menu.addAction("近期走势", self.ask_ai_for_trend)
        menu.addSeparator()

        if page.page_name in ("自选", "市场", "雷达"):
            action = menu.addAction("找同类…")
            action.triggered.connect(lambda _checked=False, it=item: self.open_reference_peer(it))
            menu.addSeparator()

        if page.config.show_add_watchlist_button:
            if page._watchlist.contains(item):
                action = menu.addAction("移出自选")
                action.triggered.connect(page.remove_from_watchlist)
            else:
                action = menu.addAction("加入自选")
                action.triggered.connect(page.add_to_watchlist)

        if page.config.show_download_button:
            action = menu.addAction("下载日K到本地")
            action.triggered.connect(page.download_selected)

        if page.config.show_backtest_button:
            action = menu.addAction("策略回测")
            action.triggered.connect(self.open_backtest_for_selected)

        if page.config.show_watchlist_move_buttons:
            if page._watchlist.contains(item):
                menu.addSeparator()
                index = page._watchlist.index_of(item)
                total = len(page.all_stocks)
                can_move = page._watchlist_groups is None or not page._watchlist_groups.is_filtering()
                if can_move and index is not None and index > 0:
                    action = menu.addAction("上移")
                    action.triggered.connect(lambda: page._watchlist.move_selected("up"))
                if can_move and index is not None and index + 1 < total:
                    action = menu.addAction("下移")
                    action.triggered.connect(lambda: page._watchlist.move_selected("down"))

        if page.page_name == "自选" and page.config.show_watchlist_groups and page._watchlist_groups is not None:
            selected = [it for it in page._table.selected_items() if page._watchlist.contains(it)]
            if not selected:
                selected = [item]
            menu.addSeparator()
            page._watchlist_groups.append_group_menu(menu, selected)

        return menu

    def open_stock_analysis(self, item: StockItem) -> None:
        page = self._p
        quote = page.quote_map.get(item.tickflow_symbol)
        show_stock_analysis_from_quotes_page(item=item, page=page, quote=quote, parent=page)

    def open_reference_peer(self, item: StockItem) -> None:
        page = self._p
        service = page._get_watchlist_service()

        def watchlist_add(symbol: str, exchange, name: str = "") -> bool:
            if service is None:
                return False
            return service.add(symbol, exchange, name)

        show_reference_peer_dialog(
            vt_symbol=item.vt_symbol,
            reference_name=item.name,
            watchlist_add=watchlist_add if service is not None else None,
            retired_workers=page._retired_workers,
            parent=page,
        )
