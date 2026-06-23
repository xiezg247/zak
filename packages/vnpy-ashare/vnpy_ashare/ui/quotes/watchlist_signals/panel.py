"""自选页独立策略信号区域（薄壳：组合 header + table_view）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol
from vnpy_ashare.config.preferences.watchlist_signal import (
    SIGNAL_PANEL_MAX_SYMBOLS,
    WatchlistSignalConfig,
    load_signal_panel_symbols,
    normalize_signal_panel_symbols,
    save_signal_panel_symbols,
)
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_signals.header import SignalPanelHeader
from vnpy_ashare.ui.quotes.watchlist_signals.table_view import SignalPanelTableView
from vnpy_common.ui.theme.manager import theme_manager


class WatchlistSignalPanel(QtWidgets.QWidget):
    """自选页信号监控区：手动名单 + 双均线策略 + 独立表格。"""

    symbols_changed = QtCore.Signal()
    enabled_changed = QtCore.Signal(bool)
    config_changed = QtCore.Signal()
    refresh_requested = QtCore.Signal()
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    register_position_requested = QtCore.Signal(str)
    ai_interpret_requested = QtCore.Signal(str)
    ai_scan_requested = QtCore.Signal()
    expansion_changed = QtCore.Signal(bool)

    def __init__(self, page: WatchlistHost) -> None:
        super().__init__(as_qwidget(page))
        self._page = page
        self._symbols: list[str] = load_signal_panel_symbols()
        self._updated_at = ""

        self.setObjectName("WatchlistSignalPanel")
        theme_manager().bind_stylesheet(self)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        self._header = SignalPanelHeader(page, self)
        self._table_view = SignalPanelTableView(page, self)

        root.addWidget(self._header)
        root.addWidget(self._table_view, stretch=1)

        self._wire()
        self._header.apply_config(page.signal_config.normalized())
        self._table_view.set_symbols(self._symbols)
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._do_render_panel)
        self._table_view.render_table()

    # ── 属性 ────────────────────────────────────────────────

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def enabled(self) -> bool:
        return self._header.is_enabled()

    def is_expanded(self) -> bool:
        return self._header.is_expanded()

    # ── 配置代理 ────────────────────────────────────────────

    def read_config(self) -> WatchlistSignalConfig:
        return self._header.read_config()

    def apply_config(self, config: WatchlistSignalConfig) -> None:
        self._header.apply_config(config)

    def sync_strategy_profile_combo(self, profile_id: str) -> None:
        self._header.sync_strategy_profile_combo(profile_id)

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        self._header.set_expanded(expanded, emit=emit)

    def sync_splitter_geometry(self) -> None:
        self._header.sync_splitter_geometry()

    def show_column_menu(self) -> None:
        self._header.show_column_menu()

    # ── 符号 CRUD ───────────────────────────────────────────

    def set_symbols(self, symbols: list[str], *, save: bool = True) -> None:
        self._symbols = normalize_signal_panel_symbols(symbols)
        if save:
            save_signal_panel_symbols(self._symbols)
        if not self._symbols:
            self._table_view.signal_filter = None
        self._table_view.set_symbols(self._symbols)
        self._table_view.render_table()

    def add_symbols(self, vt_symbols: list[str]) -> tuple[int, int]:
        added = 0
        skipped = 0
        for vt in vt_symbols:
            text = canonical_vt_symbol(str(vt or "").strip()) or str(vt or "").strip()
            if not text or text in self._symbols:
                continue
            if len(self._symbols) >= SIGNAL_PANEL_MAX_SYMBOLS:
                skipped += 1
                continue
            self._symbols.append(text)
            added += 1
        if added:
            save_signal_panel_symbols(self._symbols)
            self._table_view.set_symbols(self._symbols)
            self._table_view.render_table()
            self.symbols_changed.emit()
        return added, skipped

    def remove_symbols(self, vt_symbols: list[str]) -> int:
        removed = 0
        for vt in vt_symbols:
            text = str(vt or "").strip()
            if text and text in self._symbols:
                self._symbols.remove(text)
                removed += 1
        if removed:
            save_signal_panel_symbols(self._symbols)
            if not self._symbols:
                self._table_view.signal_filter = None
            self._table_view.set_symbols(self._symbols)
            self._table_view.render_table()
            self.symbols_changed.emit()
        return removed

    def remove_selected_symbols(self) -> int:
        return self.remove_symbols(self.selected_vt_symbols())

    def remove_with_fallback(self, fallback_vt: str | None = None) -> int:
        removed = self.remove_selected_symbols()
        if removed:
            return removed
        fallback = str(fallback_vt or "").strip()
        if fallback:
            return self.remove_symbols([fallback])
        return 0

    # ── 渲染代理 ────────────────────────────────────────────

    def set_updated_at(self, text: str) -> None:
        self._updated_at = text.strip()
        self._table_view.set_updated_at(self._updated_at)

    def render_panel(self) -> None:
        self._do_render_panel()

    def schedule_render_panel(self) -> None:
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _do_render_panel(self) -> None:
        self._table_view.set_symbols(self._symbols)
        self._table_view.render_table()
        self._table_view.sync_highlight_from_page()

    def highlight_symbol(self, vt_symbol: str | None) -> None:
        self._table_view.highlight_symbol(vt_symbol)

    def selected_vt_symbols(self) -> list[str]:
        return self._table_view.selected_vt_symbols()

    def update_rows_for_tickflow_symbols(self, tickflow_symbols: set[str]) -> None:
        self._table_view.update_rows_for_tickflow_symbols(tickflow_symbols)

    # ── 内部连线 ────────────────────────────────────────────

    def _wire(self) -> None:
        h = self._header
        t = self._table_view

        h.config_changed.connect(self._on_header_config_changed)
        h.enabled_changed.connect(self._on_header_enabled_changed)
        h.refresh_requested.connect(self.refresh_requested.emit)
        h.ai_scan_requested.connect(self.ai_scan_requested.emit)
        h.ai_clicked.connect(self._on_ai_clicked)
        h.register_position_clicked.connect(self._on_register_position_clicked_header)
        h.remove_requested.connect(self._on_remove_from_header)
        h.clear_requested.connect(self._on_clear_from_header)
        h.expansion_changed.connect(self._on_header_expansion_changed)

        t.row_activated.connect(self.row_activated.emit)
        t.row_selected.connect(self.row_selected.emit)

    # ── 连线回调 ────────────────────────────────────────────

    def _on_header_config_changed(self) -> None:
        page = self._page
        page._signals.apply_config(self._header.read_config())
        t = self._table_view
        t.set_visible_column_keys(self._header.visible_column_keys())
        self.config_changed.emit()

    def _on_header_enabled_changed(self, enabled: bool) -> None:
        self.enabled_changed.emit(enabled)

    def _on_header_expansion_changed(self, expanded: bool) -> None:
        self._table_view.set_visible(expanded)
        self.expansion_changed.emit(expanded)

    def _on_ai_clicked(self) -> None:
        symbols = self.selected_vt_symbols()
        if len(symbols) == 1:
            self.ai_interpret_requested.emit(symbols[0])
            return
        if len(symbols) > 1:
            self._page._toast.warning("AI 解读一次仅支持单只标的")
            return
        item = self._page.current_item
        if item is not None and item.vt_symbol in self._symbols:
            self.ai_interpret_requested.emit(item.vt_symbol)
            return
        self._page._toast.warning("请先在策略信号区选择标的")

    def _on_register_position_clicked_header(self) -> None:
        symbols = self.selected_vt_symbols()
        if not symbols:
            self._page._toast.warning("请先在策略信号区选择标的")
            return
        if len(symbols) > 1:
            self._page._toast.warning("登记持仓一次仅支持单只标的")
            return
        self.register_position_requested.emit(symbols[0])

    def _on_remove_from_header(self) -> None:
        item = self._page.current_item
        fallback = item.vt_symbol if item else None
        removed = self.remove_with_fallback(fallback)
        if removed:
            self._page._toast.success(f"已移出信号区 {removed} 只")
        else:
            self._page._toast.warning("请在信号区选择要移出的标的，或在自选表选中已在名单中的标的")

    def _on_clear_from_header(self) -> None:
        if not self._symbols:
            self._page._toast.info("信号区暂无监控标的")
            return
        count = len(self._symbols)
        reply = QtWidgets.QMessageBox.question(
            self,
            "清空信号区",
            f"确定移出全部 {count} 只监控标的？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.set_symbols([], save=True)
        self.symbols_changed.emit()
        self._page._toast.success(f"已清空信号区 {count} 只")
