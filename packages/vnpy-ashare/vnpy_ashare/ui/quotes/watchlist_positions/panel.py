"""自选页持仓策略区域（薄壳：组合 header + table_view）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.watchlist_position import (
    POSITION_PANEL_COLLAPSED_HEIGHT,
    WatchlistPositionConfig,
)
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.storage.repositories.positions import POSITION_MAX_ITEMS
from vnpy_ashare.trading.plan.plan_check import check_buy_against_plan
from vnpy_ashare.trading.risk.realized_pnl import today_trade_date
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_positions.dialog import PositionEditDialog
from vnpy_ashare.ui.quotes.watchlist_positions.header import PositionPanelHeader
from vnpy_ashare.ui.quotes.watchlist_positions.plan_dialog import TradingPlanDialog
from vnpy_ashare.ui.quotes.watchlist_positions.table_view import PositionPanelTableView
from vnpy_ashare.ui.quotes.watchlist_positions.trading_params_dialog import TradingParamsDialog
from vnpy_common.ui.theme.manager import theme_manager


class WatchlistPositionPanel(QtWidgets.QWidget):
    rows_changed = QtCore.Signal()
    enabled_changed = QtCore.Signal(bool)
    config_changed = QtCore.Signal()
    refresh_requested = QtCore.Signal()
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    expansion_changed = QtCore.Signal(bool)

    def __init__(self, page: WatchlistHost) -> None:
        super().__init__(as_qwidget(page))
        self._page = page

        self.setObjectName("WatchlistPositionPanel")
        theme_manager().bind_stylesheet(self)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        self._header = PositionPanelHeader(page, self)
        self._table_view = PositionPanelTableView(page, self)

        root.addWidget(self._header)
        root.addWidget(self._table_view, stretch=1)

        self._wire()
        self._header.apply_config(page.position_config.normalized())
        expanded = self._header.is_expanded()
        self._table_view.setVisible(expanded)
        self._sync_panel_geometry(expanded)
        self.render_panel()

    @property
    def enabled(self) -> bool:
        return self._header.enabled

    def is_expanded(self) -> bool:
        return self._header.is_expanded()

    def minimumHeight(self) -> int:
        return self._header.minimum_panel_height()

    def read_config(self) -> WatchlistPositionConfig:
        return self._header.read_config()

    def apply_config(self, config: WatchlistPositionConfig) -> None:
        self._header.apply_config(config)

    def sync_strategy_profile_combo(self, profile_id: str) -> None:
        self._header.sync_strategy_profile_combo(profile_id)

    def sync_follow_display(self, signal_config: WatchlistSignalConfig) -> None:
        self._header.sync_follow_display(signal_config)

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        self._header.set_expanded(expanded, emit=emit)

    def set_updated_at(self, text: str) -> None:
        self._table_view.set_updated_at(text)

    def highlight_symbol(self, vt_symbol: str) -> None:
        self._table_view.highlight_symbol(vt_symbol)

    def render_panel(self) -> None:
        self._table_view.render_table()

    def update_rows_for_tickflow_symbols(self, tickflow_symbols: set[str]) -> None:
        self._table_view.update_rows_for_tickflow_symbols(
            tickflow_symbols,
            enabled=self.enabled,
            expanded=self.is_expanded(),
        )

    def add_symbol(self, vt_symbol: str) -> bool:
        service = self._page._get_position_service()
        if service is None:
            self._page.status_label.setText("持仓服务未就绪")
            return False
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return False
        if service.contains(item.symbol, item.exchange):
            self._page._toast.warning("该标的已有持仓，请使用编辑")
            return False
        title = f"添加持仓 · {item.symbol}"
        dialog = PositionEditDialog(title=title, symbol_text=vt_symbol, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return False
        self._save_form(vt_symbol, dialog.read_form(), existing=False, existing_plan_pct=None)
        return True

    def _records(self) -> list[PositionRecord]:
        service = self._page._get_position_service()
        if service is None:
            return []
        return service.get_items()

    def _save_form(
        self,
        vt_symbol: str,
        form,
        *,
        existing: bool,
        existing_plan_pct: float | None,
    ) -> None:
        service = self._page._get_position_service()
        if service is None:
            self._page.status_label.setText("持仓服务未就绪")
            return
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            self._page._toast.warning("标的不在自选池")
            return
        error = service.validate_inputs(cost_price=form.cost_price, volume=form.volume, buy_date=form.buy_date)
        if error:
            self._page._toast.warning(error)
            return
        plan_pct = existing_plan_pct if existing else None
        if existing:
            ok = service.update(
                item.symbol,
                item.exchange,
                cost_price=form.cost_price,
                volume=form.volume,
                buy_date=form.buy_date,
                notes=form.notes,
                plan_pct=plan_pct,
            )
        else:
            ok = service.add(
                item.symbol,
                item.exchange,
                cost_price=form.cost_price,
                volume=form.volume,
                buy_date=form.buy_date,
                notes=form.notes,
                plan_pct=plan_pct,
            )
        if not ok:
            reason = service.add_failure_reason(item.symbol, item.exchange) if not existing else None
            if reason == "full":
                self._page._toast.warning(f"持仓已满（最多 {POSITION_MAX_ITEMS} 只）")
            elif reason == "duplicate":
                self._page._toast.warning("该标的已有持仓")
            elif reason == "not_in_watchlist":
                self._page._toast.warning("须先将标的加入自选池")
            else:
                self._page._toast.warning("保存失败")
            return
        if not existing:
            check = check_buy_against_plan(item.symbol, item.exchange, trade_date=today_trade_date())
            for warning in check.warnings:
                self._page._toast.warning(warning)
        self._page.status_label.setText(f"已保存持仓：{vt_symbol}")
        self.rows_changed.emit()

    def _wire(self) -> None:
        h = self._header
        t = self._table_view

        h.config_changed.connect(self.config_changed.emit)
        h.enabled_changed.connect(self.enabled_changed.emit)
        h.refresh_requested.connect(self.refresh_requested.emit)
        h.expansion_changed.connect(self._on_header_expansion_changed)
        h.add_requested.connect(self._on_add_clicked)
        h.edit_requested.connect(self._on_edit_clicked)
        h.remove_requested.connect(self._on_remove_clicked)
        h.clear_requested.connect(self._on_clear_clicked)
        h.plan_requested.connect(self._on_plan_clicked)
        h.params_requested.connect(self._on_params_clicked)

        t.row_activated.connect(self._on_row_activated)
        t.row_selected.connect(self.row_selected.emit)

    def _on_header_expansion_changed(self, expanded: bool) -> None:
        self._table_view.setVisible(expanded)
        self._sync_panel_geometry(expanded)
        self.expansion_changed.emit(expanded)

    def _sync_panel_geometry(self, expanded: bool) -> None:
        if expanded:
            self.setMinimumHeight(self._header.minimum_panel_height())
            self.setMaximumHeight(16777215)
        else:
            self.setMinimumHeight(POSITION_PANEL_COLLAPSED_HEIGHT)
            self.setMaximumHeight(POSITION_PANEL_COLLAPSED_HEIGHT + 4)

    def _on_row_activated(self, vt_symbol: str) -> None:
        self.row_activated.emit(vt_symbol)
        self._on_edit_clicked()

    def _resolve_selected_vt_symbol(self) -> str | None:
        vt_symbol = self._table_view.selected_vt_symbol()
        if not vt_symbol:
            item = self._page.current_item
            if item is not None:
                vt_symbol = item.vt_symbol
        return vt_symbol or None

    def _on_add_clicked(self) -> None:
        vt_symbol = self._resolve_selected_vt_symbol()
        if not vt_symbol:
            self._page._toast.warning("请先在自选表中选择要添加的标的")
            return
        self.add_symbol(vt_symbol)

    def _on_edit_clicked(self) -> None:
        vt_symbol = self._resolve_selected_vt_symbol()
        if not vt_symbol:
            self._page._toast.warning("请先选择要编辑的持仓")
            return
        record = next((row for row in self._records() if row.vt_symbol == vt_symbol), None)
        if record is None:
            self._page._toast.warning("该标的尚无持仓记录")
            return
        item = self._page.find_stock_item(vt_symbol)
        title = f"编辑持仓 · {item.symbol if item else vt_symbol}"
        dialog = PositionEditDialog(title=title, symbol_text=vt_symbol, record=record, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._save_form(vt_symbol, dialog.read_form(), existing=True, existing_plan_pct=record.plan_pct)

    def _on_remove_clicked(self) -> None:
        vt_symbol = self._resolve_selected_vt_symbol()
        if not vt_symbol:
            self._page._toast.warning("请先选择要移出的持仓")
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "移出持仓",
            f"确认移出 {vt_symbol} 的持仓记录？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        stock = self._page.find_stock_item(vt_symbol)
        service = self._page._get_position_service()
        if stock is None or service is None:
            return
        if service.remove(stock.symbol, stock.exchange):
            self._page.position_cache.pop(vt_symbol, None)
            self._page.status_label.setText(f"已移出持仓：{vt_symbol}")
            self.rows_changed.emit()

    def _on_clear_clicked(self) -> None:
        if not self._records():
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "清空持仓",
            "确认清空全部持仓记录？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        service = self._page._get_position_service()
        if service is None:
            return
        service.clear()
        self._page._positions.invalidate_cache()
        self._page.status_label.setText("已清空全部持仓")
        self.rows_changed.emit()

    def _on_plan_clicked(self) -> None:
        dialog = TradingPlanDialog(page=self._page, parent=self)
        dialog.exec()

    def _on_params_clicked(self) -> None:
        dialog = TradingParamsDialog(parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.render_panel()
        self.rows_changed.emit()
