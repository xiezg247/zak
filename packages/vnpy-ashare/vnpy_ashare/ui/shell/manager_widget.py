"""数据管理：交易所中文化、证券名称、精简下载/导入入口。"""

from __future__ import annotations

from datetime import datetime
from functools import partial

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.ui import QtWidgets
from vnpy_datamanager.ui.widget import DataCell, DateRangeDialog
from vnpy_datamanager.ui.widget import ManagerWidget as VnpyManagerWidget

from vnpy_ashare.ai.data_manager_context import sync_data_manager_context
from vnpy_ashare.config import EXCHANGE_CN_NAMES
from vnpy_ashare.ui.shell.manager_workers import (
    DeleteBarsWorker,
    ExportCsvWorker,
    LoadBarsWorker,
    TreeRefreshPayload,
    TreeRefreshWorker,
    _overview_group_key,
)
from vnpy_ashare.ui.styles import apply_legacy_page_style, style_legacy_push_buttons
from vnpy_common.ui.feedback import PageToastHost, TaskGuard, confirm_action, page_notify

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


class ManagerWidget(VnpyManagerWidget):
    def init_ui(self) -> None:
        self.setWindowTitle("数据管理")
        self.init_tree()
        self.init_table()

        self._refresh_button = QtWidgets.QPushButton("刷新")
        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.clicked.connect(self.refresh_tree)

        hint_label = QtWidgets.QLabel(_DOWNLOAD_HINT)
        hint_label.setWordWrap(True)
        hint_label.setObjectName("PageHint")

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 8)
        toolbar.addWidget(self._refresh_button)
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
        root.addLayout(body, stretch=1)
        self._toast = PageToastHost(self)
        root.addWidget(self._toast)
        self.setLayout(root)

        self._task_guard = TaskGuard(self._toast)
        self._active_worker_attr: str | None = None
        self._refresh_worker: TreeRefreshWorker | None = None
        self._load_worker: LoadBarsWorker | None = None
        self._export_worker: ExportCsvWorker | None = None
        self._delete_worker: DeleteBarsWorker | None = None

        apply_legacy_page_style(self, page_id="DataManagerPage")
        style_legacy_push_buttons(self)

    def init_tree(self) -> None:
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(_TREE_LABELS))
        self.tree.setHeaderLabels(_TREE_LABELS)

    def activate(self) -> None:
        self.refresh_tree()

    def _lock_widgets(self) -> list[QtWidgets.QWidget]:
        return [self.tree, self.table, self._refresh_button]

    def _begin_task(
        self,
        message: str,
        *,
        worker_attr: str,
        cancellable: bool = True,
    ) -> bool:
        if self._task_guard.active:
            page_notify(self, "请等待当前任务完成", level="warning")
            return False
        self._active_worker_attr = worker_attr

        def on_cancel() -> None:
            worker = getattr(self, worker_attr, None)
            if worker is not None and hasattr(worker, "request_cancel"):
                worker.request_cancel()

        self._task_guard.begin(
            message,
            widgets=self._lock_widgets(),
            on_cancel=on_cancel if cancellable else None,
        )
        return True

    def _finish_task(self, *, cancelled_message: str = "任务已取消") -> bool:
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        self._active_worker_attr = None
        if cancelled:
            self._toast.info(cancelled_message)
        return cancelled

    def refresh_tree(self) -> None:
        if not self._begin_task("正在刷新数据列表…", worker_attr="_refresh_worker"):
            return

        worker = TreeRefreshWorker(self.engine.main_engine)
        self._refresh_worker = worker

        def on_finished(payload: object) -> None:
            if self._refresh_worker is worker:
                self._refresh_worker = None
            if self._finish_task(cancelled_message="刷新已取消"):
                return
            if isinstance(payload, TreeRefreshPayload):
                self._apply_tree_refresh(payload)
                sync_data_manager_context(self.engine.main_engine)
                self._toast.success(f"已加载 {len(payload.rows)} 条数据记录")

        def on_failed(msg: str) -> None:
            if self._refresh_worker is worker:
                self._refresh_worker = None
            if self._finish_task(cancelled_message="刷新已取消"):
                return
            self._toast.error(msg or "刷新失败")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _apply_tree_refresh(self, payload: TreeRefreshPayload) -> None:
        self.tree.clear()
        interval_childs: dict[str, QtWidgets.QTreeWidgetItem] = {}
        exchange_childs: dict[tuple[str, Exchange], QtWidgets.QTreeWidgetItem] = {}

        for key in _INTERVAL_GROUP_LABELS:
            interval_child = QtWidgets.QTreeWidgetItem()
            interval_childs[key] = interval_child
            interval_child.setText(0, _INTERVAL_GROUP_LABELS[key])

        for row in payload.rows:
            group = _overview_group_key(row.period)
            interval_child = interval_childs.get(group)
            if interval_child is None:
                continue

            exchange_key = (group, row.exchange)
            exchange_child = exchange_childs.get(exchange_key)
            if exchange_child is None:
                exchange_child = QtWidgets.QTreeWidgetItem(interval_child)
                exchange_child.setText(0, row.exchange.value)
                exchange_childs[exchange_key] = exchange_child

            item = QtWidgets.QTreeWidgetItem(exchange_child)
            item.setText(1, f"{row.symbol}.{row.exchange.value}")
            item.setText(2, row.symbol)
            item.setText(3, row.stock_name)
            item.setText(4, row.exchange.value)
            item.setText(5, str(row.count))
            item.setText(6, row.start.strftime("%Y-%m-%d %H:%M:%S"))
            item.setText(7, row.end.strftime("%Y-%m-%d %H:%M:%S"))

            output_button = QtWidgets.QPushButton("导出")
            output_button.setObjectName("SecondaryButton")
            output_button.clicked.connect(partial(self.output_data, row.symbol, row.exchange, row.interval, row.start, row.end))
            show_button = QtWidgets.QPushButton("查看")
            show_button.setObjectName("SecondaryButton")
            show_button.clicked.connect(partial(self.show_data, row.symbol, row.exchange, row.interval, row.start, row.end))
            delete_button = QtWidgets.QPushButton("删除")
            delete_button.setObjectName("DangerButton")
            delete_button.clicked.connect(partial(self.delete_data, row.symbol, row.exchange, row.interval))

            self.tree.setItemWidget(item, 8, show_button)
            self.tree.setItemWidget(item, 9, output_button)
            self.tree.setItemWidget(item, 10, delete_button)

        self.tree.addTopLevelItems(list(interval_childs.values()))
        for interval_child in interval_childs.values():
            interval_child.setExpanded(True)

        for i in range(self.tree.topLevelItemCount()):
            self._localize_item(self.tree.topLevelItem(i))

    def output_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> None:
        dialog = DateRangeDialog(start, end, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        start, end = dialog.get_date_range()

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出数据", "", "CSV(*.csv)")
        if not path:
            return

        label = f"{symbol}.{exchange.value}"
        if not self._begin_task(f"正在导出 {label}…", worker_attr="_export_worker"):
            return

        worker = ExportCsvWorker(
            self.engine,
            path=path,
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end,
        )
        self._export_worker = worker

        def on_finished(ok: bool) -> None:
            if self._export_worker is worker:
                self._export_worker = None
            if self._finish_task(cancelled_message="导出已取消"):
                return
            if ok:
                self._toast.success(f"已导出 CSV：{path}")
            else:
                self._toast.error("导出失败：文件可能已在其他程序中打开")

        def on_failed(msg: str) -> None:
            if self._export_worker is worker:
                self._export_worker = None
            if self._finish_task(cancelled_message="导出已取消"):
                return
            self._toast.error(msg or "导出失败")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def show_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> None:
        dialog = DateRangeDialog(start, end, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        start, end = dialog.get_date_range()

        label = f"{symbol}.{exchange.value}"
        if not self._begin_task(f"正在加载 {label} K 线…", worker_attr="_load_worker"):
            return

        worker = LoadBarsWorker(
            self.engine,
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end,
        )
        self._load_worker = worker

        def on_finished(bars: list) -> None:
            if self._load_worker is worker:
                self._load_worker = None
            if self._finish_task(cancelled_message="加载已取消"):
                return
            self._apply_bars_to_table(bars)
            self._toast.success(f"已加载 {len(bars)} 条 K 线")

        def on_failed(msg: str) -> None:
            if self._load_worker is worker:
                self._load_worker = None
            if self._finish_task(cancelled_message="加载已取消"):
                return
            self._toast.error(msg or "加载失败")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _apply_bars_to_table(self, bars: list) -> None:
        self.table.setRowCount(0)
        self.table.setRowCount(len(bars))
        for row, bar in enumerate(bars):
            self.table.setItem(row, 0, DataCell(bar.datetime.strftime("%Y-%m-%d %H:%M:%S")))
            self.table.setItem(row, 1, DataCell(str(bar.open_price)))
            self.table.setItem(row, 2, DataCell(str(bar.high_price)))
            self.table.setItem(row, 3, DataCell(str(bar.low_price)))
            self.table.setItem(row, 4, DataCell(str(bar.close_price)))
            self.table.setItem(row, 5, DataCell(str(bar.volume)))
            self.table.setItem(row, 6, DataCell(str(bar.turnover)))
            self.table.setItem(row, 7, DataCell(str(bar.open_interest)))

    def delete_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
    ) -> None:
        if self._task_guard.active:
            page_notify(self, "请等待当前任务完成", level="warning")
            return

        period_label = interval.value
        if not confirm_action(
            self,
            "删除确认",
            f"确定删除 {symbol} {exchange.value} {period_label} 的全部本地 K 线数据？\n\n此操作不可恢复。",
            confirm_text="删除",
            destructive=True,
        ):
            return

        if not self._begin_task(
            f"正在删除 {symbol}.{exchange.value}…",
            worker_attr="_delete_worker",
            cancellable=False,
        ):
            return

        worker = DeleteBarsWorker(
            self.engine,
            symbol=symbol,
            exchange=exchange,
            interval=interval,
        )
        self._delete_worker = worker

        def on_finished(count: int) -> None:
            if self._delete_worker is worker:
                self._delete_worker = None
            if self._finish_task():
                return
            self._toast.success(f"已删除 {count} 条数据")
            self.refresh_tree()

        def on_failed(msg: str) -> None:
            if self._delete_worker is worker:
                self._delete_worker = None
            if self._finish_task():
                return
            self._toast.error(msg or "删除失败")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _localize_item(self, item) -> None:
        text = item.text(0)
        if text in _VALUE_TO_CN:
            item.setText(0, _VALUE_TO_CN[text])

        ex_col = item.text(4)
        if ex_col in _VALUE_TO_CN:
            item.setText(4, _VALUE_TO_CN[ex_col])

        for i in range(item.childCount()):
            self._localize_item(item.child(i))
