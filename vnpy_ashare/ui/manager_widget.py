"""数据管理：交易所中文化、证券名称、精简下载/导入入口。"""

from __future__ import annotations

from functools import partial

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.ui import QtWidgets
from vnpy_datamanager.ui.widget import ManagerWidget as VnpyManagerWidget

from vnpy_ashare.config import EXCHANGE_CN_NAMES
from vnpy_ashare.engine_access import get_bar_service
from vnpy_ashare.minute_periods import bar_interval, is_daily_scope
from vnpy_ashare.ui.styles import apply_legacy_page_style, style_legacy_push_buttons

_VALUE_TO_CN = {ex.value: name for ex, name in EXCHANGE_CN_NAMES.items()}

_TREE_LABELS: list[str] = [
    "数据",
    "本地代码",
    "代码",
    "证券名称",
    "交易所",
    "数据量",
    "开始时间",
    "结束时间",
    "",
    "",
    "",
]

_DOWNLOAD_HINT = "K 线下载与补全请使用「自选 / 本地」页，或「工具 → 立即执行 → 下载自选日 K / 同步 A 股列表」"

_INTERVAL_GROUP_LABELS: dict[str, str] = {
    "daily": "日线",
    "1m": "分钟线",
}


def _overview_group_key(period: str) -> str:
    if is_daily_scope(period):
        return "daily"
    return period


class ManagerWidget(VnpyManagerWidget):
    def init_ui(self) -> None:
        self.setWindowTitle("数据管理")
        self.init_tree()
        self.init_table()

        refresh_button = QtWidgets.QPushButton("刷新")
        refresh_button.setObjectName("SecondaryButton")
        refresh_button.clicked.connect(self.refresh_tree)

        hint_label = QtWidgets.QLabel(_DOWNLOAD_HINT)
        hint_label.setWordWrap(True)
        hint_label.setObjectName("PageHint")

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 8)
        toolbar.addWidget(refresh_button)
        toolbar.addWidget(hint_label, stretch=1)

        body = QtWidgets.QHBoxLayout()
        self.tree.setObjectName("DataManagerTree")
        self.table.setObjectName("DataManagerTable")
        body.addWidget(self.tree)
        body.addWidget(self.table)

        root = QtWidgets.QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addLayout(toolbar)
        root.addLayout(body)
        self.setLayout(root)
        apply_legacy_page_style(self, page_id="DataManagerPage")
        style_legacy_push_buttons(self)

    def init_tree(self) -> None:
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(_TREE_LABELS))
        self.tree.setHeaderLabels(_TREE_LABELS)

    def activate(self) -> None:
        self.refresh_tree()

    def _bar_service(self):
        return get_bar_service(getattr(self, "main_engine", None))

    def refresh_tree(self) -> None:
        self.tree.clear()
        bar_svc = self._bar_service()
        name_map = bar_svc.build_symbol_name_map() if bar_svc else self._fallback_symbol_name_map()

        group_keys = ["daily", "1m"]
        interval_childs: dict[str, QtWidgets.QTreeWidgetItem] = {}
        exchange_childs: dict[tuple[str, Exchange], QtWidgets.QTreeWidgetItem] = {}

        for key in group_keys:
            interval_child = QtWidgets.QTreeWidgetItem()
            interval_childs[key] = interval_child
            interval_child.setText(0, _INTERVAL_GROUP_LABELS[key])

        scopes = ["daily", "1m"]
        seen: set[tuple[str, Exchange, str]] = set()
        for scope in scopes:
            overviews = bar_svc.iter_overviews(scope) if bar_svc else self._fallback_iter_overviews(scope)
            for overview in overviews:
                dedupe_key = (overview.symbol, overview.exchange, overview.period)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                group = _overview_group_key(overview.period)
                interval_child = interval_childs.get(group)
                if interval_child is None:
                    continue

                exchange_key = (group, overview.exchange)
                exchange_child = exchange_childs.get(exchange_key)
                if exchange_child is None:
                    exchange_child = QtWidgets.QTreeWidgetItem(interval_child)
                    exchange_child.setText(0, overview.exchange.value)
                    exchange_childs[exchange_key] = exchange_child

                item = QtWidgets.QTreeWidgetItem(exchange_child)
                stock_name = name_map.get((overview.symbol, overview.exchange), "")

                item.setText(1, f"{overview.symbol}.{overview.exchange.value}")
                item.setText(2, overview.symbol)
                item.setText(3, stock_name)
                item.setText(4, overview.exchange.value)
                item.setText(5, str(overview.count))
                item.setText(6, overview.start.strftime("%Y-%m-%d %H:%M:%S"))
                item.setText(7, overview.end.strftime("%Y-%m-%d %H:%M:%S"))

                if is_daily_scope(overview.period):
                    interval = Interval.DAILY
                else:
                    interval = bar_interval(overview.period)

                output_button = QtWidgets.QPushButton("导出")
                output_button.setObjectName("SecondaryButton")
                output_button.clicked.connect(
                    partial(
                        self.output_data,
                        overview.symbol,
                        overview.exchange,
                        interval,
                        overview.start,
                        overview.end,
                    )
                )
                show_button = QtWidgets.QPushButton("查看")
                show_button.setObjectName("SecondaryButton")
                show_button.clicked.connect(
                    partial(
                        self.show_data,
                        overview.symbol,
                        overview.exchange,
                        interval,
                        overview.start,
                        overview.end,
                    )
                )
                delete_button = QtWidgets.QPushButton("删除")
                delete_button.setObjectName("DangerButton")
                delete_button.clicked.connect(
                    partial(
                        self.delete_data,
                        overview.symbol,
                        overview.exchange,
                        interval,
                    )
                )

                self.tree.setItemWidget(item, 8, show_button)
                self.tree.setItemWidget(item, 9, output_button)
                self.tree.setItemWidget(item, 10, delete_button)

        self.tree.addTopLevelItems(list(interval_childs.values()))
        for interval_child in interval_childs.values():
            interval_child.setExpanded(True)

        for i in range(self.tree.topLevelItemCount()):
            self._localize_item(self.tree.topLevelItem(i))

        from vnpy_ashare.ai.data_manager_context import sync_data_manager_context

        sync_data_manager_context(getattr(self, "main_engine", None))

    def _localize_item(self, item) -> None:
        text = item.text(0)
        if text in _VALUE_TO_CN:
            item.setText(0, _VALUE_TO_CN[text])

        ex_col = item.text(4)
        if ex_col in _VALUE_TO_CN:
            item.setText(4, _VALUE_TO_CN[ex_col])

        for i in range(item.childCount()):
            self._localize_item(item.child(i))

    @staticmethod
    def _fallback_symbol_name_map():
        """BarService 不可用时（无 Engine）经 bar_access 读取。"""
        from vnpy_ashare.bar_access import build_symbol_name_map

        return build_symbol_name_map()

    @staticmethod
    def _fallback_iter_overviews(scope: str):
        from vnpy_ashare.bar_access import iter_bar_overviews

        return iter_bar_overviews(scope=scope)
