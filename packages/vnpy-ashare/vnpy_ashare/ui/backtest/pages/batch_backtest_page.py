"""批量回测对比页（独立大表格）。"""

from __future__ import annotations

from typing import Any

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from strategies.registry import STRATEGY_REGISTRY
from vnpy_ashare.ai.context.backtest import sync_batch_compare_context
from vnpy_ashare.backtest.run_store import (
    BatchBacktestSession,
    delete_batch,
    list_batch_sessions,
    list_runs_by_batch,
)
from vnpy_ashare.ui.backtest.table.batch_backtest_table import BatchBacktestTableWidget, record_to_row
from vnpy_common.ui.feedback import PageToastHost, confirm_action

_SOURCE_LABELS = {
    "batch_watchlist": "自选",
    "batch_screener": "选股",
}


def _strategy_title(class_name: str) -> str:
    try:
        for meta in STRATEGY_REGISTRY.values():
            if meta.class_name == class_name:
                return str(meta.title)
    except Exception:
        pass
    return class_name


def _source_label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source or "—")


def _toolbar_separator() -> QtWidgets.QFrame:
    sep = QtWidgets.QFrame()
    sep.setObjectName("ToolbarSeparator")
    sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    sep.setFixedHeight(22)
    return sep


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
        hint = QtWidgets.QLabel("批量回测结果横向对比 · 按收益与风险指标排序")
        hint.setObjectName("PageHint")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(hint)
        header.addStretch()
        root.addLayout(header)

        self.summary_bar = QtWidgets.QWidget()
        self.summary_bar.setObjectName("BatchCompareSummaryBar")
        summary_layout = QtWidgets.QHBoxLayout(self.summary_bar)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(16)
        self._summary_strategy = QtWidgets.QLabel("—")
        self._summary_strategy.setObjectName("StatsLabel")
        self._summary_period = QtWidgets.QLabel("—")
        self._summary_period.setObjectName("StatsLabel")
        self._summary_counts = QtWidgets.QLabel("—")
        self._summary_counts.setObjectName("StatsLabel")
        for label in (self._summary_strategy, self._summary_period, self._summary_counts):
            summary_layout.addWidget(label)
        summary_layout.addStretch()
        self.summary_bar.setVisible(False)
        root.addWidget(self.summary_bar)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)
        self.refresh_btn = QtWidgets.QPushButton("刷新")
        self.refresh_btn.setObjectName("SecondaryButton")
        self.refresh_btn.clicked.connect(self.refresh_sessions)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()
        toolbar.addWidget(_toolbar_separator())
        self.delete_btn = QtWidgets.QPushButton("删除批次")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._delete_current_batch)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)
        root.addLayout(toolbar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        session_panel = QtWidgets.QWidget()
        session_panel.setObjectName("BatchCompareSessionPanel")
        session_panel.setMinimumWidth(240)
        session_panel.setMaximumWidth(300)
        session_layout = QtWidgets.QVBoxLayout(session_panel)
        session_layout.setContentsMargins(12, 10, 12, 10)
        session_layout.setSpacing(8)
        session_title = QtWidgets.QLabel("历史批次")
        session_title.setObjectName("ScreenerSectionLabel")
        session_layout.addWidget(session_title)
        self.session_list = QtWidgets.QListWidget()
        self.session_list.setObjectName("BatchSessionListWidget")
        self.session_list.currentItemChanged.connect(self._on_session_changed)
        session_layout.addWidget(self.session_list, stretch=1)
        splitter.addWidget(session_panel)

        result_panel = QtWidgets.QWidget()
        result_panel.setObjectName("BatchCompareResultPanel")
        result_layout = QtWidgets.QVBoxLayout(result_panel)
        result_layout.setContentsMargins(12, 10, 12, 10)
        result_layout.setSpacing(8)
        result_title = QtWidgets.QLabel("对比结果")
        result_title.setObjectName("ScreenerSectionLabel")
        result_layout.addWidget(result_title)
        self.result_table = BatchBacktestTableWidget()
        result_layout.addWidget(self.result_table, stretch=1)
        splitter.addWidget(result_panel)
        splitter.setStretchFactor(0, 0)
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
            title = _strategy_title(session.strategy)
            source = _source_label(session.source)
            line2 = f"{source} · {session.success_count}/{session.row_count} 成功 · {session.start_date} ~ {session.end_date}"
            line3 = session.created_at[5:16]
            item = QtWidgets.QListWidgetItem(f"{title}\n{line2}\n{line3}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, session.batch_id)
            item.setToolTip(
                f"策略：{title}（{session.strategy}）\n"
                f"来源：{source}\n"
                f"区间：{session.start_date} ~ {session.end_date}\n"
                f"时间：{session.created_at}\n"
                f"批次 ID：{session.batch_id}"
            )
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
            self.summary_bar.setVisible(False)
            self.delete_btn.setEnabled(False)
            sync_batch_compare_context(None, [], self.main_engine)
            return

        records = list_runs_by_batch(batch_id)
        rows = [record_to_row(record) for record in records]
        self._current_rows = rows
        self.result_table.load_rows(rows)

        session = self._find_session(batch_id)
        if session is not None:
            title = _strategy_title(session.strategy)
            source = _source_label(session.source)
            self._summary_strategy.setText(f"策略：{title}")
            self._summary_period.setText(f"区间：{session.start_date} ~ {session.end_date}")
            self._summary_counts.setText(f"来源：{source} · 共 {session.row_count} 只 · 成功 {session.success_count} · 失败 {session.error_count}")
        else:
            self._summary_strategy.setText(f"批次：{batch_id[:8]}…")
            self._summary_period.setText("—")
            self._summary_counts.setText(f"共 {len(rows)} 只")

        self.summary_bar.setVisible(True)
        self.delete_btn.setEnabled(True)
        sync_batch_compare_context(session, rows, self.main_engine)

    def _find_session(self, batch_id: str) -> BatchBacktestSession | None:
        for session in list_batch_sessions(limit=100):
            if session.batch_id == batch_id:
                return session
        return None

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
