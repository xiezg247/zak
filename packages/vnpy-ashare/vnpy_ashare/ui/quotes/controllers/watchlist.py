"""自选池 UI 控制器（委托 WatchlistService）。"""

from __future__ import annotations

from typing import cast

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.runtime import format_vt_symbol_cn
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.services.watchlist import WATCHLIST_MAX_ITEMS, WatchlistService
from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


class WatchlistController:
    """封装自选 CRUD 与按钮状态，供 QuotesPage 调用。"""

    def __init__(self, page: WatchlistHost) -> None:
        self._page = page
        self.keys: set[tuple[str, Exchange]] = set()

    def _service(self) -> WatchlistService | None:
        return self._page._get_watchlist_service()

    def refresh_keys(self) -> None:
        service = self._service()
        if service is None:
            self.keys = set()
            return
        self.keys = {(row["symbol"], Exchange(row["exchange"])) for row in service.get_items()}

    def contains(self, item: StockItem) -> bool:
        """标的是否在自选池（自选页列表即自选池，不依赖 keys 缓存）。"""
        if self._page.page_name == "自选":
            return True
        return (item.symbol, item.exchange) in self.keys

    def update_action_buttons(self, item: StockItem | None) -> None:
        page = self._page
        if page.config.show_add_watchlist_button:
            if item is None:
                page.add_watchlist_button.setEnabled(False)
            else:
                key = (item.symbol, item.exchange)
                page.add_watchlist_button.setEnabled(key not in self.keys and len(self.keys) < WATCHLIST_MAX_ITEMS)
        if page.config.show_remove_watchlist_button:
            selected = page._table.selected_items()
            count = len(selected) if len(selected) > 1 else (1 if (selected or item is not None) else 0)
            page.remove_watchlist_button.setEnabled(count > 0)
            page.remove_watchlist_button.setText("移出自选" if count <= 1 else f"移出 {count} 只")

    def _pool_from_service(self) -> list[StockItem]:
        service = self._service()
        if service is None:
            return []
        return [
            StockItem(
                symbol=row["symbol"],
                exchange=Exchange(row["exchange"]),
                name=row["name"],
            )
            for row in service.get_items()
        ]

    def _apply_pool(self, pool: list[StockItem]) -> None:
        """从 service 结果刷新自选列表 UI（避免 load_stock_list 全量重载）。"""
        page = self._page
        bootstrap = getattr(page, "_watchlist_bootstrap", None)
        if isinstance(bootstrap, WatchlistBootstrapCoordinator):
            bootstrap.on_pool_ready(page, pool, source="pool_mutation")
            return
        page.watchlist_pool_stocks = pool
        if page._watchlist_groups is not None:
            page._watchlist_groups.on_stock_list_loaded(pool)
        else:
            page.all_stocks = pool
            page.apply_filter()
        self.refresh_keys()
        page._update_action_buttons()
        feature = getattr(page, "_watchlist_feature", None)
        if feature is not None:
            feature.refresh_context_bar()

    def add_selected(self) -> None:
        if not self._page.current_item:
            return
        service = self._service()
        if service is None:
            self._page.status_label.setText("自选服务未就绪")
            return

        item = self._page.current_item
        quote = self._page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        if not service.add(item.symbol, item.exchange, name):
            reason = service.add_failure_reason(item.symbol, item.exchange)
            if reason == "full":
                self._page.status_label.setText(f"自选池已满（最多 {WATCHLIST_MAX_ITEMS} 只）")
            else:
                self._page.status_label.setText(f"{format_vt_symbol_cn(item.symbol, item.exchange)} 已在自选池")
            return
        self.refresh_keys()
        self._page._update_action_buttons()
        if self._page._watchlist_groups is not None:
            self._page._watchlist_groups.add_item_to_active_group(item.symbol, item.exchange)
        status = f"已加入自选：{format_vt_symbol_cn(item.symbol, item.exchange)}"
        if self._page._watchlist_groups is not None and self._page._watchlist_groups.is_filtering():
            status += f"（已加入分组「{self._page._watchlist_groups.active_group_label()}」）"
        self._page.status_label.setText(status)

    def remove_selected(self) -> None:
        self.remove_items()

    def remove_items(self, context_item: StockItem | None = None) -> None:
        page = self._page
        targets = self._remove_targets(context_item)
        if not targets:
            toast = getattr(page, "_toast", None)
            if toast is not None:
                toast.info("请先选择要移出的标的")
            else:
                page.status_label.setText("请先选择要移出的标的")
            return

        service = self._service()
        if service is None:
            page.status_label.setText("自选服务未就绪")
            return

        if len(targets) > 1:
            answer = QtWidgets.QMessageBox.question(
                cast(QtWidgets.QWidget, page),
                "移出自选",
                f"确定从自选池移出 {len(targets)} 只标的？",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return

        if not self._confirm_remove_positions(targets):
            return

        removed_vts: list[str] = []
        removed_labels: list[str] = []
        failed = 0
        for item in targets:
            if not service.remove(item.symbol, item.exchange):
                failed += 1
                continue
            removed_vts.append(item.vt_symbol)
            removed_labels.append(format_vt_symbol_cn(item.symbol, item.exchange))

        if not removed_labels:
            page.status_label.setText("移出失败：标的不在自选池")
            return

        if len(removed_labels) == 1:
            status = f"已移出自选：{removed_labels[0]}"
        else:
            status = f"已移出自选 {len(removed_labels)} 只"
        if failed:
            status += f"（{failed} 只失败）"
        page.status_label.setText(status)
        self._apply_pool(self._pool_from_service())
        bootstrap = getattr(page, "_watchlist_bootstrap", None)
        if isinstance(bootstrap, WatchlistBootstrapCoordinator) and removed_vts:
            bootstrap.invalidate_symbols(page, removed_vts)
        if page.config.show_watchlist_signals:
            page._signals.on_symbols_changed()
        if not page.display_stocks:
            page.current_item = None
            if page.depth_panel is not None:
                page.depth_panel.clear()

    def _remove_targets(self, context_item: StockItem | None = None) -> list[StockItem]:
        selected = self._page._table.selected_items()
        if len(selected) > 1:
            return selected
        if context_item is not None:
            return [context_item]
        if selected:
            return selected
        if self._page.current_item is not None:
            return [self._page.current_item]
        return []

    def _confirm_remove_positions(self, targets: list[StockItem]) -> bool:
        page = self._page
        position_service = page._get_position_service()
        if position_service is None:
            return True

        with_positions = [
            item for item in targets if position_service.contains(item.symbol, item.exchange)
        ]
        if not with_positions:
            return True

        if len(with_positions) == 1:
            item = with_positions[0]
            message = f"{format_vt_symbol_cn(item.symbol, item.exchange)} 仍有持仓记录，是否一并移出？"
        else:
            message = f"其中 {len(with_positions)} 只有持仓记录，是否一并移出持仓？"
        answer = QtWidgets.QMessageBox.question(
            cast(QtWidgets.QWidget, page),
            "移出自选",
            message,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return False

        for item in with_positions:
            position_service.remove(item.symbol, item.exchange)
            page.position_cache.pop(item.vt_symbol, None)
        panel = getattr(page, "position_panel", None)
        if panel is not None:
            panel.render_panel()
        return True
