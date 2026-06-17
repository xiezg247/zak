"""参考选股（找同类）对话框。"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.screener.reference.reference_peer import (
    REFERENCE_PEER_TOP_N_MAX,
    ReferencePeerRunResult,
    clamp_reference_peer_top_n,
    env_default_reference_peer_top_n,
)
from vnpy_ashare.storage.repositories.watchlist import WATCHLIST_MAX_ITEMS, watchlist_add_failure_reason
from vnpy_ashare.ui.screener.widgets.screener_results_table import (
    configure_screener_results_table,
    iter_checked_table_rows,
    populate_screener_results_table,
    toggle_select_all_table_rows,
    update_select_all_button,
    wire_screener_results_table,
)
from vnpy_ashare.ui.screener.workers.reference_peer_worker import ReferencePeerWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread
from vnpy_common.ui.theme import theme_manager

_RESULT_COLUMNS: list[tuple[str, str]] = [
    ("symbol", "代码"),
    ("name", "名称"),
    ("similarity_score", "相似分"),
    ("hit_reason", "入选原因"),
    ("pe_ttm", "PE TTM"),
    ("momentum_5d", "5日涨跌%"),
]

_SETTINGS = get_settings()
_SETTINGS_TOP_N_KEY = "reference_peer/top_n"


def _load_top_n_default() -> int:
    saved = _SETTINGS.value(_SETTINGS_TOP_N_KEY)
    if saved is not None:
        try:
            return clamp_reference_peer_top_n(int(saved))
        except (TypeError, ValueError):
            pass
    return env_default_reference_peer_top_n()


def _save_top_n(value: int) -> None:
    _SETTINGS.setValue(_SETTINGS_TOP_N_KEY, clamp_reference_peer_top_n(value))


class ReferencePeerDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        vt_symbol: str,
        reference_name: str,
        watchlist_add: Callable[[str, Exchange, str], bool] | None = None,
        retired_workers: list[QtCore.QThread] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vt_symbol = vt_symbol
        self._reference_name = reference_name
        self._watchlist_add = watchlist_add
        self._retired_workers: list[QtCore.QThread] = retired_workers if retired_workers is not None else []
        self._worker: ReferencePeerWorker | None = None
        self._result: ReferencePeerRunResult | None = None
        self._closing = False

        title = reference_name or vt_symbol
        self.setWindowTitle(f"找同类 · {title}")
        self.setMinimumSize(760, 520)
        theme_manager().bind_stylesheet(self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._head_label = QtWidgets.QLabel(f"标杆：{self._reference_name}（{self._vt_symbol}）")
        self._head_label.setObjectName("ResultSummary")
        layout.addWidget(self._head_label)

        config_row = QtWidgets.QHBoxLayout()
        config_row.addWidget(QtWidgets.QLabel("返回条数"))
        self._top_n_spin = QtWidgets.QSpinBox()
        self._top_n_spin.setRange(1, REFERENCE_PEER_TOP_N_MAX)
        self._top_n_spin.setValue(_load_top_n_default())
        config_row.addWidget(self._top_n_spin)
        config_row.addStretch()
        self._start_btn = QtWidgets.QPushButton("开始对标")
        self._start_btn.setObjectName("PrimaryRunButton")
        self._start_btn.clicked.connect(self._start_worker)
        config_row.addWidget(self._start_btn)
        layout.addLayout(config_row)

        self._log = QtWidgets.QPlainTextEdit()
        self._log.setObjectName("ScreenerHint")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)

        self._summary_label = QtWidgets.QLabel("设定返回条数后点击「开始对标」")
        self._summary_label.setObjectName("ScreenerHint")
        layout.addWidget(self._summary_label)

        self._table = QtWidgets.QTableWidget(0, 1)
        configure_screener_results_table(self._table)
        layout.addWidget(self._table, stretch=1)

        action_row = QtWidgets.QHBoxLayout()
        self._select_all_btn = QtWidgets.QPushButton("全选")
        self._select_all_btn.setObjectName("SecondaryButton")
        self._select_all_btn.clicked.connect(self._select_all)
        self._select_all_btn.setEnabled(False)
        wire_screener_results_table(self._table, select_all_btn=self._select_all_btn)
        action_row.addWidget(self._select_all_btn)

        self._add_watchlist_btn = QtWidgets.QPushButton("加入自选")
        self._add_watchlist_btn.setObjectName("SecondaryButton")
        self._add_watchlist_btn.clicked.connect(self._add_to_watchlist)
        self._add_watchlist_btn.setEnabled(False)
        action_row.addWidget(self._add_watchlist_btn)
        action_row.addStretch()

        self._close_btn = QtWidgets.QPushButton("关闭")
        self._close_btn.clicked.connect(self.reject)
        action_row.addWidget(self._close_btn)
        layout.addLayout(action_row)

    def _append_log(self, message: str) -> None:
        self._log.appendPlainText(message)

    def _set_running(self, running: bool) -> None:
        self._top_n_spin.setEnabled(not running)
        self._start_btn.setEnabled(not running)

    def _start_worker(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        top_n = clamp_reference_peer_top_n(self._top_n_spin.value())
        self._top_n_spin.setValue(top_n)
        _save_top_n(top_n)
        self._set_running(True)
        self._select_all_btn.setEnabled(False)
        self._add_watchlist_btn.setEnabled(False)
        self._table.setRowCount(0)
        self._log.clear()
        self._summary_label.setText("正在对标…")
        self._append_log(f"开始参考选股，返回前 {top_n} 条…")
        worker = ReferencePeerWorker(
            self._vt_symbol,
            reference_name=self._reference_name,
            top_n=top_n,
        )
        self._worker = worker
        worker.progress.connect(self._append_log)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.start()

    def _cleanup_worker(self, worker: ReferencePeerWorker | None) -> None:
        if worker is None:
            return
        self._disconnect_worker(worker)
        release_thread(self._retired_workers, worker)

    def _disconnect_worker(self, worker: ReferencePeerWorker) -> None:
        for signal, slot in (
            (worker.progress, self._append_log),
            (worker.finished, self._on_finished),
            (worker.failed, self._on_failed),
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass

    def _on_finished(self, result: ReferencePeerRunResult) -> None:
        if self._closing:
            return
        worker = self._worker
        self._worker = None
        self._result = result
        self._head_label.setText(
            f"标杆：{result.reference_name}（{result.reference_vt_symbol}） · 行业 {result.reference_industry} · 交易日 {result.trade_date}"
        )
        if not result.rows:
            self._summary_label.setText("未找到符合条件的同类标的")
            self._set_running(False)
            self._cleanup_worker(worker)
            return

        self._populate_results(result.rows)
        self._summary_label.setText(f"命中 {len(result.rows)} 条 · 扫描同业 {result.total_scanned} 只")
        self._select_all_btn.setEnabled(True)
        self._add_watchlist_btn.setEnabled(self._watchlist_add is not None)
        self._set_running(False)
        self._cleanup_worker(worker)

    def _on_failed(self, message: str) -> None:
        if self._closing:
            return
        worker = self._worker
        self._worker = None
        self._append_log(f"失败：{message}")
        self._summary_label.setText(message)
        self._set_running(False)
        page_notify(self, message, level="warning", title="参考选股")
        self._cleanup_worker(worker)

    def _populate_results(self, rows: list[dict[str, Any]]) -> None:
        self._table.blockSignals(True)
        try:
            populate_screener_results_table(self._table, rows, _RESULT_COLUMNS)
        finally:
            self._table.blockSignals(False)
        update_select_all_button(self._table, self._select_all_btn)

    def _select_all(self) -> None:
        toggle_select_all_table_rows(self._table)
        update_select_all_button(self._table, self._select_all_btn)

    def _add_to_watchlist(self) -> None:
        if self._watchlist_add is None:
            return
        selected = iter_checked_table_rows(self._table)
        if not selected:
            page_notify(self, "请先勾选要加入自选的标的")
            return
        added = skipped = 0
        full_hit = False
        for row in selected:
            item = parse_stock_symbol(str(row.get("vt_symbol", "")))
            if item is None:
                skipped += 1
                continue
            name = str(row.get("name", "") or item.name)
            if self._watchlist_add(item.symbol, item.exchange, name):
                added += 1
            else:
                reason = watchlist_add_failure_reason(item.symbol, item.exchange)
                if reason == "full":
                    full_hit = True
                    break
                skipped += 1
        message = f"新加入 {added} 只"
        if skipped:
            message += f" · 跳过 {skipped} 只"
        if full_hit:
            message += f" · 自选已满（最多 {WATCHLIST_MAX_ITEMS} 只）"
        self._summary_label.setText(message)

    def closeEvent(self, event) -> None:
        self._closing = True
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.requestInterruption()
            self._cleanup_worker(worker)
        super().closeEvent(event)


def show_reference_peer_dialog(
    *,
    vt_symbol: str,
    reference_name: str = "",
    watchlist_add: Callable[[str, Exchange, str], bool] | None = None,
    retired_workers: list[QtCore.QThread] | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    dialog = ReferencePeerDialog(
        vt_symbol=vt_symbol,
        reference_name=reference_name,
        watchlist_add=watchlist_add,
        retired_workers=retired_workers,
        parent=parent,
    )
    dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    dialog.show()
