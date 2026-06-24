"""行情表格列配置与表头。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.ui.quotes.controllers.table.base import TableControllerBase
from vnpy_ashare.ui.quotes.page.config import (
    ALL_TAIL_COLUMNS,
    DEFAULT_WATCHLIST_COLUMNS,
    MARKET_VISIBLE_COLUMNS,
    ensure_columns_from_template,
    ensure_industry_board_columns,
)
from vnpy_ashare.ui.quotes.table.columns import QUOTE_TABLE_COLUMNS


class TableColumnsMixin(TableControllerBase):
    def _default_main_columns(self) -> list[str]:
        page = self._p
        all_keys = [c.key for c in QUOTE_TABLE_COLUMNS]
        if page.page_name == "自选":
            default_main = [k for k in DEFAULT_WATCHLIST_COLUMNS if k in all_keys]
        else:
            default_main = [k for k in MARKET_VISIBLE_COLUMNS if k in all_keys]
        default_main = self._strip_signal_columns(default_main)
        for required in ("index", "symbol", "name"):
            if required in all_keys and required not in default_main:
                default_main.insert(0, required)
        if page.page_name == "市场":
            default_main = ensure_industry_board_columns(default_main, available_keys=set(all_keys))
        return default_main

    def init_columns(self) -> None:
        self.visible_columns = self._default_main_columns()
        self.visible_tail_columns = self._default_tail_columns()
        self.restore_column_config()
        self.sync_tail_columns_with_config()

    def _allowed_tail_column_keys(self) -> set[str]:
        page = self._p
        if page.config.use_local_table:
            return set()
        allowed: set[str] = set()
        if page.config.show_local_column:
            allowed.add("local")
        if page.config.show_fill_button and not page.config.use_local_table:
            allowed.update(("start", "end", "count", "status"))
        return allowed

    def _sanitize_tail_columns(self) -> bool:
        allowed = self._allowed_tail_column_keys()
        sanitized = [key for key in self.visible_tail_columns if key in allowed]
        if sanitized == self.visible_tail_columns:
            return False
        self.visible_tail_columns = sanitized
        return True

    def sync_tail_columns_with_config(self) -> bool:
        """按页面配置剔除无效尾列；有变更时写回 QSettings 并提示需重建表头。"""
        if not self._sanitize_tail_columns():
            return False
        self.save_column_config()
        return True

    def _default_tail_columns(self) -> list[str]:
        page = self._p
        if page.config.use_local_table:
            return []
        if page.config.show_fill_button and not page.config.use_local_table:
            return ["start", "end", "count", "status"]
        if page.config.show_local_column:
            return ["local"]
        return []

    def build_visible_headers(self) -> list[str]:
        col_map = {c.key: c.header for c in QUOTE_TABLE_COLUMNS}
        headers = [col_map[k] for k in self.visible_columns]
        for key in self.visible_tail_columns:
            headers.append(ALL_TAIL_COLUMNS.get(key, key))
        return headers

    def _all_quote_column_keys(self) -> list[str]:
        return [c.key for c in QUOTE_TABLE_COLUMNS]

    def column_settings_key(self) -> str:
        return f"quotes/columns/{self._p.page_name}"

    def save_column_config(self) -> None:
        page = self._p
        if not page.config.column_configurable:
            return
        settings = get_settings()
        settings.setValue(
            self.column_settings_key(),
            ",".join(self.visible_columns) + "|" + ",".join(self.visible_tail_columns),
        )

    def restore_column_config(self) -> None:
        page = self._p
        if not page.config.column_configurable:
            return
        settings = get_settings()
        value = settings.value(self.column_settings_key())
        if not isinstance(value, str):
            return
        parts = value.split("|", 1)
        if parts[0]:
            saved_cols = [k for k in parts[0].split(",") if k]
            all_keys = {c.key for c in QUOTE_TABLE_COLUMNS}
            valid_cols = [k for k in saved_cols if k in all_keys and k != "index"]
            valid_cols = self._strip_signal_columns(valid_cols)
            for required in ("symbol", "name"):
                if required in all_keys and required not in valid_cols:
                    valid_cols.insert(0, required)
            valid_cols.insert(0, "index")
            before = list(valid_cols)
            if page.page_name == "自选":
                if "market_board" in valid_cols:
                    valid_cols.remove("market_board")
                valid_cols = ensure_columns_from_template(
                    valid_cols,
                    DEFAULT_WATCHLIST_COLUMNS,
                    available_keys=all_keys,
                )
            elif page.page_name == "市场":
                valid_cols = ensure_industry_board_columns(valid_cols, available_keys=all_keys)
            self.visible_columns = valid_cols
            if valid_cols != before:
                self.save_column_config()
        if len(parts) > 1 and parts[1]:
            self.visible_tail_columns = [k for k in parts[1].split(",") if k in ALL_TAIL_COLUMNS]

    def apply_header_layout(self, *, column_count: int | None = None) -> None:
        page = self._p
        view = self._view()
        header = view.horizontalHeader()
        header.setStretchLastSection(False)
        if page.config.use_local_table:
            for idx, mode in enumerate(
                [
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.Stretch,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                ]
            ):
                if idx < self._model().column_count():
                    header.setSectionResizeMode(idx, mode)
            return
        count = column_count if column_count is not None else self._model().column_count()
        for col in range(count):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        if "name" in self.visible_columns:
            name_idx = self.visible_columns.index("name")
            header.setSectionResizeMode(name_idx, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def show_column_menu(self) -> None:
        page = self._p
        menu = QtWidgets.QMenu(page)
        col_map = {c.key: c.header for c in QUOTE_TABLE_COLUMNS}

        for key in [c.key for c in QUOTE_TABLE_COLUMNS]:
            if key == "index":
                continue
            if key in self._signal_column_keys():
                continue
            action = menu.addAction(col_map.get(key, key))
            action.setCheckable(True)
            action.setChecked(key in self.visible_columns)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.on_column_toggle(k, checked))

        allowed_tail = self._allowed_tail_column_keys()
        if allowed_tail:
            menu.addSeparator()
            for key, header in ALL_TAIL_COLUMNS.items():
                if key not in allowed_tail:
                    continue
                action = menu.addAction(header)
                action.setCheckable(True)
                action.setChecked(key in self.visible_tail_columns)
                action.setData(key)
                action.triggered.connect(lambda checked, k=key: self.on_tail_column_toggle(k, checked))

        button = page.column_button
        if button is None:
            return
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def on_column_toggle(self, key: str, checked: bool) -> None:
        if checked and key not in self.visible_columns:
            self.visible_columns.append(key)
        elif not checked and key in self.visible_columns:
            self.visible_columns.remove(key)
        self.rebuild_table()

    def on_tail_column_toggle(self, key: str, checked: bool) -> None:
        if key not in self._allowed_tail_column_keys():
            return
        if checked and key not in self.visible_tail_columns:
            self.visible_tail_columns.append(key)
        elif not checked and key in self.visible_tail_columns:
            self.visible_tail_columns.remove(key)
        self.rebuild_table()

    def rebuild_table(self) -> None:
        headers = self.build_visible_headers()
        self._model().set_headers(headers)
        self.apply_header_layout(column_count=len(headers))
        self.render_table()
