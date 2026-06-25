"""自选分组 UI 控制器。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.watchlist_groups import (
    load_active_watchlist_group_id,
    save_active_watchlist_group_id,
)
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.services.watchlist import WatchlistGroupRecord, load_watchlist_group_member_keys
from vnpy_ashare.trading.risk.metrics import read_total_capital
from vnpy_ashare.trading.risk.plan_position import format_group_position_tab_label, summarize_group_position
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_common.ui.feedback import page_notify


class WatchlistGroupController(QtCore.QObject):
    """自选页分组筛选与成员管理。"""

    groups_changed = QtCore.Signal()

    def __init__(self, page: WatchlistHost) -> None:
        super().__init__(as_qwidget(page))
        self._page = page
        self._groups: list[WatchlistGroupRecord] = []
        self._active_group_id: str | None = load_active_watchlist_group_id()
        self._member_keys: set[tuple[str, str]] = set()

    @property
    def active_group_id(self) -> str | None:
        return self._active_group_id

    def is_filtering(self) -> bool:
        return bool(self._active_group_id)

    def active_group_label(self) -> str:
        if not self._active_group_id:
            return "自选"
        for group in self._groups:
            if group.id == self._active_group_id:
                return group.name
        return "自选"

    def _service(self):
        return self._page._get_watchlist_service()

    def refresh_groups(self) -> None:
        service = self._service()
        if service is None:
            self._groups = []
            self._member_keys = set()
            return
        self._groups = service.list_groups()
        if self._active_group_id and not any(group.id == self._active_group_id for group in self._groups):
            self._active_group_id = None
            save_active_watchlist_group_id(None)
        self._reload_member_keys()
        self._populate_tab_bar()

    def _reload_member_keys(self) -> None:
        service = self._service()
        if service is None or not self._active_group_id:
            self._member_keys = set()
            return
        self._member_keys = service.group_member_keys(self._active_group_id)

    def wire(self) -> None:
        tab_bar = self._page.watchlist_group_tab_bar
        if tab_bar is None:
            return
        tab_bar.group_selected.connect(self._on_tab_selected)
        tab_bar.add_requested.connect(self._on_add_group)
        tab_bar.rename_requested.connect(self._on_rename_group)
        tab_bar.delete_requested.connect(self._on_delete_group)
        tab_bar.position_cap_requested.connect(self._on_set_group_position_cap)
        self.refresh_groups()

    def _populate_tab_bar(self) -> None:
        tab_bar = self._page.watchlist_group_tab_bar
        service = self._service()
        if tab_bar is None or service is None:
            return
        tab_bar.rebuild(
            self._groups,
            self._active_group_id,
            max_groups=service.max_groups,
            tab_labels=self._group_tab_labels(),
        )
        self._page._update_action_buttons()

    def _position_records(self):
        service = self._page._get_position_service()
        if service is None:
            return []
        return service.get_items()

    def _group_tab_labels(self) -> dict[str, str]:
        records = self._position_records()
        if not records:
            return {}
        service = self._service()
        if service is None:
            return {}
        total_capital = read_total_capital()
        labels: dict[str, str] = {}
        for group in self._groups:
            member_keys = load_watchlist_group_member_keys(group.id)
            summary = summarize_group_position(
                group_id=group.id,
                member_keys=member_keys,
                records=records,
                position_cache=self._page.position_cache,
                total_capital=total_capital,
                position_cap_pct=group.position_cap_pct,
            )
            if summary.position_count <= 0 and summary.plan_cap_pct is None:
                continue
            labels[group.id] = format_group_position_tab_label(group.name, summary)
        return labels

    def _on_tab_selected(self, group_id: str) -> None:
        normalized = str(group_id or "").strip() or None
        if normalized == self._active_group_id:
            return
        self._active_group_id = normalized
        save_active_watchlist_group_id(self._active_group_id)
        self._reload_member_keys()
        self.apply_display_stocks()
        self._page._update_action_buttons()

    def _prompt_name(self, *, title: str, label: str, initial: str = "") -> str | None:
        text, ok = QtWidgets.QInputDialog.getText(as_qwidget(self._page), title, label, text=initial)
        if not ok:
            return None
        normalized = str(text or "").strip()
        return normalized or None

    def _on_add_group(self) -> None:
        service = self._service()
        if service is None:
            self._page.status_label.setText("自选服务未就绪")
            return
        name = self._prompt_name(title="新建分组", label="分组名称：")
        if name is None:
            return
        group_id = service.create_group(name)
        if group_id is None:
            page_notify(
                as_qwidget(self._page),
                "无法创建分组（名称重复或已达上限）",
                level="warning",
            )
            return
        self._active_group_id = group_id
        save_active_watchlist_group_id(group_id)
        self.refresh_groups()
        self.apply_display_stocks()
        self.groups_changed.emit()
        self._page.status_label.setText(f"已创建分组「{name}」")

    def _on_rename_group(self, group_id: str) -> None:
        service = self._service()
        if service is None:
            return
        group = next((item for item in self._groups if item.id == group_id), None)
        if group is None:
            return
        name = self._prompt_name(title="重命名分组", label="分组名称：", initial=group.name)
        if name is None:
            return
        if not service.rename_group(group_id, name):
            page_notify(as_qwidget(self._page), "重命名失败（名称可能重复）", level="warning")
            return
        self.refresh_groups()
        self.groups_changed.emit()
        self._page.status_label.setText(f"分组已重命名为「{name}」")

    def _on_delete_group(self, group_id: str) -> None:
        service = self._service()
        if service is None:
            return
        group = next((item for item in self._groups if item.id == group_id), None)
        if group is None:
            return
        answer = QtWidgets.QMessageBox.question(
            as_qwidget(self._page),
            "删除分组",
            f"确定删除分组「{group.name}」？\n标的仍保留在自选池与其它分组中。",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if not service.delete_group(group_id):
            page_notify(as_qwidget(self._page), "删除分组失败", level="warning")
            return
        if self._active_group_id == group_id:
            self._active_group_id = None
            save_active_watchlist_group_id(None)
        self.refresh_groups()
        self.apply_display_stocks()
        self.groups_changed.emit()
        self._page.status_label.setText(f"已删除分组「{group.name}」")

    def _on_set_group_position_cap(self, group_id: str) -> None:
        service = self._service()
        if service is None:
            return
        group = next((item for item in self._groups if item.id == group_id), None)
        if group is None:
            return
        initial = ""
        if group.position_cap_pct is not None:
            initial = str(int(round(group.position_cap_pct * 100)))
        text, ok = QtWidgets.QInputDialog.getText(
            as_qwidget(self._page),
            "设置仓位上限",
            f"分组「{group.name}」计划总仓位上限（%，留空清除）：",
            text=initial,
        )
        if not ok:
            return
        normalized = str(text or "").strip()
        cap_pct = None
        if normalized:
            try:
                pct_value = float(normalized)
            except ValueError:
                page_notify(as_qwidget(self._page), "请输入有效数字", level="warning")
                return
            if pct_value <= 0 or pct_value > 100:
                page_notify(as_qwidget(self._page), "上限须在 1–100% 之间", level="warning")
                return
            cap_pct = pct_value / 100.0
        if not service.set_group_position_cap(group_id, cap_pct):
            page_notify(as_qwidget(self._page), "保存仓位上限失败", level="warning")
            return
        self.refresh_groups()
        self.groups_changed.emit()
        if cap_pct is None:
            self._page.status_label.setText(f"已清除分组「{group.name}」仓位上限")
        else:
            self._page.status_label.setText(f"分组「{group.name}」仓位上限 {int(cap_pct * 100)}%")

    def filter_stocks(self, stocks: list[StockItem]) -> list[StockItem]:
        if not self._active_group_id:
            return list(stocks)
        filtered: list[StockItem] = []
        for stock in stocks:
            key = (stock.symbol, stock.exchange.name)
            if key in self._member_keys:
                filtered.append(stock)
        return filtered

    def apply_display_stocks(self) -> None:
        page = self._page
        pool = list(getattr(page, "watchlist_pool_stocks", page.all_stocks))
        page.all_stocks = self.filter_stocks(pool)
        page.apply_filter()
        page._update_action_buttons()

    def on_stock_list_loaded(self, stocks: list[StockItem]) -> None:
        self._page.watchlist_pool_stocks = list(stocks)
        self._reload_member_keys()
        self.apply_display_stocks()

    def add_item_to_active_group(self, symbol: str, exchange: Exchange) -> bool:
        if not self._active_group_id:
            return False
        service = self._service()
        if service is None:
            return False
        return bool(service.add_to_group(self._active_group_id, symbol, exchange))

    def append_group_menu(self, menu: QtWidgets.QMenu, items: list[StockItem]) -> None:
        service = self._service()
        if service is None:
            return
        targets = list(items)
        if not targets:
            return
        title = "加入分组" if len(targets) == 1 else f"加入分组（{len(targets)} 只）"
        submenu = menu.addMenu(title)
        if not self._groups:
            placeholder = submenu.addAction("暂无分组，请先新建")
            placeholder.setEnabled(False)
            return
        if len(targets) == 1:
            self._append_single_group_menu(submenu, service, targets[0])
        else:
            self._append_multi_group_menu(submenu, service, targets)

    def _append_single_group_menu(
        self,
        submenu: QtWidgets.QMenu,
        service,
        item: StockItem,
    ) -> None:
        current_ids = service.group_ids_for_item(item.symbol, item.exchange)

        def _toggle(group_id: str, checked: bool) -> None:
            updated = set(service.group_ids_for_item(item.symbol, item.exchange))
            if checked:
                updated.add(group_id)
            else:
                updated.discard(group_id)
            service.set_item_groups(item.symbol, item.exchange, updated)
            self._after_group_membership_changed(f"已更新 {item.name or item.symbol} 的分组")

        for group in self._groups:
            action = submenu.addAction(group.name)
            action.setCheckable(True)
            action.setChecked(group.id in current_ids)
            action.triggered.connect(
                lambda checked, group_id=group.id: _toggle(group_id, bool(checked)),
            )

    def _append_multi_group_menu(
        self,
        submenu: QtWidgets.QMenu,
        service,
        items: list[StockItem],
    ) -> None:
        def _toggle(group_id: str, group_name: str, checked: bool) -> None:
            for item in items:
                updated = set(service.group_ids_for_item(item.symbol, item.exchange))
                if checked:
                    updated.add(group_id)
                else:
                    updated.discard(group_id)
                service.set_item_groups(item.symbol, item.exchange, updated)
            self._after_group_membership_changed(f"已更新 {len(items)} 只标的的分组「{group_name}」")

        for group in self._groups:
            in_group = sum(1 for item in items if group.id in service.group_ids_for_item(item.symbol, item.exchange))
            action = submenu.addAction(group.name)
            action.setCheckable(True)
            action.setChecked(in_group == len(items))
            action.triggered.connect(
                lambda checked, group_id=group.id, group_name=group.name: _toggle(
                    group_id,
                    group_name,
                    bool(checked),
                ),
            )

    def _after_group_membership_changed(self, status: str) -> None:
        self._reload_member_keys()
        self.apply_display_stocks()
        self._page.status_label.setText(status)
        feature = getattr(self._page, "_watchlist_feature", None)
        if feature is not None:
            feature.refresh_context_bar()

    def filtered_vt_symbols(self) -> tuple[str, ...] | None:
        if not self._active_group_id:
            return None
        return tuple(f"{symbol}.{exchange}" for symbol, exchange in sorted(self._member_keys))

    def select_group_tab(self, group_id: str | None) -> None:
        self._on_tab_selected(group_id or "")

    def select_all_tab(self) -> None:
        self.select_group_tab(None)
