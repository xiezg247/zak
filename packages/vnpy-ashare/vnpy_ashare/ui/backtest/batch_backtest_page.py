"""批量回测对比页（独立大表格）。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.backtest_context import sync_batch_compare_context
from vnpy_ashare.app.events import EVENT_OPEN_BACKTEST, BacktestRequest
from vnpy_ashare.backtest.run_store import (
    BatchBacktestSession,
    delete_batch,
    list_batch_sessions,
    list_runs_by_batch,
)
from vnpy_ashare.screener.export import export_rows_to_csv
from vnpy_ashare.ui.backtest.batch_backtest_table import BatchBacktestTableWidget, record_to_row
from vnpy_common.ui.feedback import PageToastHost, confirm_action


class BatchBacktestPageWidget(QtWidgets.QWidget):
    """左侧导航「回测对比」页。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")
        self._current_batch_id: str | None = None
        self._current_rows: list[Any] = []
        self._build_ui()
        self.refresh_sessions()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("回测对比")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        toolbar = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("刷新")
        self.refresh_btn.setObjectName("SecondaryButton")
        self.refresh_btn.clicked.connect(self.refresh_sessions)
        toolbar.addWidget(self.refresh_btn)

        self.open_backtest_btn = QtWidgets.QPushButton("策略回测")
        self.open_backtest_btn.setObjectName("SecondaryButton")
        self.open_backtest_btn.clicked.connect(self._open_selected_backtest)
        self.open_backtest_btn.setEnabled(False)
        toolbar.addWidget(self.open_backtest_btn)

        self.export_btn = QtWidgets.QPushButton("导出 CSV")
        self.export_btn.setObjectName("SecondaryButton")
        self.export_btn.clicked.connect(self._export_csv)
        self.export_btn.setEnabled(False)
        toolbar.addWidget(self.export_btn)

        self.delete_btn = QtWidgets.QPushButton("删除批次")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._delete_current_batch)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        toolbar.addStretch()
        self.summary_label = QtWidgets.QLabel("选择左侧批次查看对比结果")
        self.summary_label.setObjectName("PageHint")
        toolbar.addWidget(self.summary_label)
        root.addLayout(toolbar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        session_panel = QtWidgets.QWidget()
        session_layout = QtWidgets.QVBoxLayout(session_panel)
        session_layout.setContentsMargins(0, 0, 8, 0)
        session_title = QtWidgets.QLabel("批量回测批次")
        session_title.setObjectName("ScreenerSectionLabel")
        session_layout.addWidget(session_title)
        self.session_list = QtWidgets.QListWidget()
        self.session_list.setObjectName("BatchSessionListWidget")
        self.session_list.currentItemChanged.connect(self._on_session_changed)
        session_layout.addWidget(self.session_list, stretch=1)
        splitter.addWidget(session_panel)

        self.result_table = BatchBacktestTableWidget()
        self.result_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.result_table.row_activated.connect(self._open_backtest_for_symbol)
        splitter.addWidget(self.result_table)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 900])
        root.addWidget(splitter, stretch=1)

        self._toast = PageToastHost(self)
        root.addWidget(self._toast)

    def refresh_sessions(self) -> None:
        current_id = self._current_batch_id
        self.session_list.clear()
        sessions = list_batch_sessions(limit=50)
        selected_row = -1
        for index, session in enumerate(sessions):
            subtitle = f"{session.success_count}/{session.row_count} 成功 · {session.start_date}~{session.end_date} · {session.created_at[5:16]}"
            item = QtWidgets.QListWidgetItem(f"{session.strategy}\n{subtitle}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, session.batch_id)
            item.setToolTip(f"策略 {session.strategy}\n来源 {session.source} · {session.created_at}\n批次 ID {session.batch_id}")
            self.session_list.addItem(item)
            if session.batch_id == current_id:
                selected_row = index
        if selected_row >= 0:
            self.session_list.setCurrentRow(selected_row)
        elif sessions:
            self.session_list.setCurrentRow(0)
        else:
            self._load_batch(None)

    def show_batch(self, batch_id: str) -> None:
        for row in range(self.session_list.count()):
            item = self.session_list.item(row)
            if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == batch_id:
                self.session_list.setCurrentRow(row)
                return
        self.refresh_sessions()
        for row in range(self.session_list.count()):
            item = self.session_list.item(row)
            if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == batch_id:
                self.session_list.setCurrentRow(row)
                return

    def _on_session_changed(
        self,
        current: QtWidgets.QListWidgetItem | None,
        _previous: QtWidgets.QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._load_batch(None)
            return
        batch_id = current.data(QtCore.Qt.ItemDataRole.UserRole)
        self._load_batch(str(batch_id) if batch_id else None)

    def _load_batch(self, batch_id: str | None) -> None:
        self._current_batch_id = batch_id
        if not batch_id:
            self._current_rows = []
            self.result_table.setRowCount(0)
            self.summary_label.setText("暂无批量回测记录")
            self.export_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.open_backtest_btn.setEnabled(False)
            sync_batch_compare_context(None, [], self.main_engine)
            return

        records = list_runs_by_batch(batch_id)
        rows = [record_to_row(record) for record in records]
        self._current_rows = rows
        self.result_table.load_rows(rows)

        session = self._find_session(batch_id)
        if session is not None:
            self.summary_label.setText(
                f"{session.strategy} · {session.row_count} 只 · "
                f"成功 {session.success_count} · 失败 {session.error_count} · "
                f"{session.start_date}~{session.end_date}"
            )
        else:
            self.summary_label.setText(f"批次 {batch_id[:8]}… · {len(rows)} 只")

        self.export_btn.setEnabled(bool(rows))
        self.delete_btn.setEnabled(True)
        self.open_backtest_btn.setEnabled(False)
        sync_batch_compare_context(session, rows, self.main_engine)

    def _find_session(self, batch_id: str) -> BatchBacktestSession | None:
        for session in list_batch_sessions(limit=100):
            if session.batch_id == batch_id:
                return session
        return None

    def _on_table_selection_changed(self) -> None:
        self.open_backtest_btn.setEnabled(self.result_table.selected_vt_symbol() is not None)

    def _open_selected_backtest(self) -> None:
        vt_symbol = self.result_table.selected_vt_symbol()
        if vt_symbol:
            self._open_backtest_for_symbol(vt_symbol)

    def _open_backtest_for_symbol(self, vt_symbol: str) -> None:
        self.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(
                    vt_symbol=vt_symbol,
                    source_page="回测对比",
                ),
            )
        )

    def _export_csv(self) -> None:
        if not self._current_rows:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出批量回测",
            "batch_backtest_compare.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        export_rows_to_csv([row.to_dict() for row in self._current_rows], path)
        self._toast.success(f"已导出 CSV：{path}")

    def _delete_current_batch(self) -> None:
        if not self._current_batch_id:
            return
        if not confirm_action(
            self,
            "确认删除",
            "删除当前批次的全部回测记录？",
            confirm_text="删除",
            destructive=True,
        ):
            return
        delete_batch(self._current_batch_id)
        self._current_batch_id = None
        self.refresh_sessions()
        self._toast.success("批次已删除")

    def activate(self) -> None:
        self.refresh_sessions()
        if self._current_batch_id:
            sync_batch_compare_context(
                self._find_session(self._current_batch_id),
                self._current_rows,
                self.main_engine,
            )

    def deactivate(self) -> None:
        pass
