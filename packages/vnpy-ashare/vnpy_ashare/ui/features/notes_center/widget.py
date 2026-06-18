"""笔记中心主面板。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_note_service
from vnpy_ashare.domain.models.stock_note import StockNoteIndexRow
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.features.notes_center.memo_view import NotesCenterMemoView
from vnpy_ashare.ui.features.notes_center.reports_view import NotesCenterReportsView
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost
from vnpy_ashare.ui.features.stock_analysis.open import show_stock_analysis_vt_symbol
from vnpy_ashare.ui.quotes.stock_notes.ai_assist import (
    NoteAiWorker,
    apply_expanded_memo,
    build_journal_polish_messages,
    build_memo_expand_messages,
    build_quote_snapshot_for_item,
    get_llm_config,
)
from vnpy_ashare.ui.quotes.stock_notes.journal_tab import StockNoteJournalTab
from vnpy_common.paths import BACKUP_DIR
from vnpy_common.ui.dialog_shell import build_panel_footer
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.panel_widgets import panel_status_label, section_title
from vnpy_common.ui.qt_helpers import release_thread
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.services.note import NoteService

_FILTER_ALL = "all"
_FILTER_MEMO = "memo"
_FILTER_JOURNAL = "journal"
_FILTER_REPORT = "report"

_SYMBOL_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1
_EXCHANGE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 2


class NotesCenterWidget(QtWidgets.QWidget):
    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine | None,
        *,
        focus_watchlist: Callable[[str, str], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NotesCenterWidget")
        self._main_engine = main_engine
        self._event_engine = event_engine
        self._focus_watchlist = focus_watchlist
        self._rows: list[StockNoteIndexRow] = []
        self._current_row: StockNoteIndexRow | None = None
        self._ai_worker: NoteAiWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []

        self._search_edit = QtWidgets.QLineEdit(self)
        self._search_edit.setObjectName("NotesCenterSearch")
        self._search_edit.setPlaceholderText("搜索代码、名称或备忘摘要…")
        self._search_edit.textChanged.connect(self._apply_filters)

        self._filter_combo = QtWidgets.QComboBox(self)
        self._filter_combo.addItem("全部", _FILTER_ALL)
        self._filter_combo.addItem("仅有备忘", _FILTER_MEMO)
        self._filter_combo.addItem("仅有流水", _FILTER_JOURNAL)
        self._filter_combo.addItem("仅有报告", _FILTER_REPORT)
        self._filter_combo.currentIndexChanged.connect(self._apply_filters)

        self._symbol_list = QtWidgets.QListWidget(self)
        self._symbol_list.setObjectName("NotesCenterSymbolList")
        self._symbol_list.currentItemChanged.connect(self._on_symbol_changed)

        left_panel = QtWidgets.QWidget(self)
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self._search_edit)
        left_layout.addWidget(self._filter_combo)
        left_layout.addWidget(self._symbol_list, stretch=1)

        self._detail_title = section_title("选择左侧标的查看笔记")
        self._detail_title.setObjectName("NotesCenterDetailTitle")

        self._memo_view = NotesCenterMemoView(self)
        self._journal_view = StockNoteJournalTab(self)
        self._reports_view = NotesCenterReportsView(self)

        self._tabs = QtWidgets.QTabWidget(self)
        self._tabs.setObjectName("NotesCenterTabs")
        self._tabs.addTab(self._memo_view, "备忘")
        self._tabs.addTab(self._journal_view, "流水")
        self._tabs.addTab(self._reports_view, "分析报告")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        right_panel = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self._detail_title)
        right_layout.addWidget(self._tabs, stretch=1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.setObjectName("NotesCenterSplitter")
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 720])

        self._status_label = panel_status_label("就绪")
        self._refresh_button = QtWidgets.QPushButton("刷新", self)
        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.clicked.connect(self.reload_index)

        self._watchlist_button = QtWidgets.QPushButton("在自选查看", self)
        self._watchlist_button.setObjectName("SecondaryButton")
        self._watchlist_button.clicked.connect(self._open_in_watchlist)

        self._analysis_button = QtWidgets.QPushButton("个股分析", self)
        self._analysis_button.setObjectName("SecondaryButton")
        self._analysis_button.clicked.connect(self._open_stock_analysis)

        self._export_button = QtWidgets.QPushButton("导出 Markdown", self)
        self._export_button.setObjectName("SecondaryButton")
        self._export_button.clicked.connect(self._export_current)

        footer = build_panel_footer(
            self._status_label,
            self._refresh_button,
            self._watchlist_button,
            self._analysis_button,
            self._export_button,
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(10)
        layout.addWidget(splitter, stretch=1)
        layout.addWidget(footer)

        self._memo_view.memo_changed.connect(self._on_memo_changed)
        self._memo_view.ai_expand_requested.connect(self._on_ai_expand_memo)
        self._journal_view.entry_submitted.connect(self._on_entry_submitted)
        self._journal_view.entry_delete_requested.connect(self._on_entry_delete)
        self._journal_view.ai_polish_requested.connect(self._on_ai_polish_journal)
        self._reports_view.report_delete_requested.connect(self._on_report_delete)

        theme_manager().bind_stylesheet(self)
        self._set_detail_enabled(False)

    def focus_tab(self, tab: str) -> None:
        mapping = {"memo": 0, "journal": 1, "reports": 2}
        index = mapping.get(tab.strip().lower(), 0)
        self._tabs.setCurrentIndex(index)

    def activate(self) -> None:
        self.reload_index()

    def select_vt_symbol(self, vt_symbol: str) -> None:
        parts = vt_symbol.strip().split(".", 1)
        if len(parts) != 2:
            return
        symbol, exchange = parts[0], parts[1]
        for index in range(self._symbol_list.count()):
            item = self._symbol_list.item(index)
            if item is None:
                continue
            if item.data(_SYMBOL_ROLE) == symbol and item.data(_EXCHANGE_ROLE) == exchange:
                self._symbol_list.setCurrentItem(item)
                return
        self._pending_select = (symbol, exchange)

    def reload_index(self) -> None:
        service = self._note_service()
        if service is None:
            self._status_label.setText("笔记服务未就绪")
            return
        self._rows = service.list_index_rows()
        self._apply_filters()
        count = len(self._rows)
        self._status_label.setText(f"共 {count} 个标的含笔记")

    def _note_service(self) -> NoteService | None:
        return get_note_service(self._main_engine)

    def _apply_filters(self) -> None:
        query = self._search_edit.text().strip().casefold()
        filter_key = str(self._filter_combo.currentData() or _FILTER_ALL)
        filtered: list[StockNoteIndexRow] = []
        for row in self._rows:
            if filter_key == _FILTER_MEMO and not row.has_memo:
                continue
            if filter_key == _FILTER_JOURNAL and row.entry_count <= 0:
                continue
            if filter_key == _FILTER_REPORT and row.report_count <= 0:
                continue
            if query:
                haystack = " ".join(
                    [
                        row.symbol,
                        row.exchange,
                        row.name,
                        row.memo_preview,
                        row.vt_symbol,
                    ]
                ).casefold()
                if query not in haystack:
                    continue
            filtered.append(row)

        current_key: tuple[str, str] | None = None
        if self._current_row is not None:
            current_key = (self._current_row.symbol, self._current_row.exchange)

        self._symbol_list.blockSignals(True)
        self._symbol_list.clear()
        selected_item: QtWidgets.QListWidgetItem | None = None
        for row in filtered:
            item = QtWidgets.QListWidgetItem(_format_symbol_item(row))
            item.setData(_SYMBOL_ROLE, row.symbol)
            item.setData(_EXCHANGE_ROLE, row.exchange)
            item.setToolTip(row.memo_preview or f"{row.entry_count} 条流水")
            self._symbol_list.addItem(item)
            if current_key == (row.symbol, row.exchange):
                selected_item = item
        self._symbol_list.blockSignals(False)

        if selected_item is not None:
            self._symbol_list.setCurrentItem(selected_item)
        elif self._symbol_list.count() > 0:
            self._symbol_list.setCurrentRow(0)
        else:
            self._current_row = None
            self._clear_detail()

        if not filtered:
            self._status_label.setText("暂无匹配的笔记")

    def _on_symbol_changed(
        self,
        current: QtWidgets.QListWidgetItem | None,
        _previous: QtWidgets.QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._current_row = None
            self._clear_detail()
            return
        symbol = str(current.data(_SYMBOL_ROLE) or "")
        exchange = str(current.data(_EXCHANGE_ROLE) or "")
        row = next(
            (item for item in self._rows if item.symbol == symbol and item.exchange == exchange),
            None,
        )
        if row is None:
            self._current_row = None
            self._clear_detail()
            return
        self._memo_view.flush_if_dirty()
        self._current_row = row
        self._load_detail(row)

    def _load_detail(self, row: StockNoteIndexRow) -> None:
        service = self._note_service()
        if service is None:
            return
        try:
            exchange = Exchange[row.exchange]
        except KeyError:
            self._status_label.setText(f"未知交易所: {row.exchange}")
            return

        title = row.name or row.symbol
        self._detail_title.setText(f"{title}  {row.vt_symbol}")
        bundle = service.get_bundle(row.symbol, exchange, entry_limit=200)
        memo_body = bundle.memo.body if bundle.memo is not None else ""
        self._memo_view.load_body(memo_body)
        self._journal_view.load_entries(bundle.entries)
        reports = service.list_reports(row.symbol, exchange, limit=200)
        self._reports_view.load_reports(reports)
        self._set_detail_enabled(True)

    def _clear_detail(self) -> None:
        self._detail_title.setText("选择左侧标的查看笔记")
        self._memo_view.clear()
        self._journal_view.clear()
        self._reports_view.clear()
        self._set_detail_enabled(False)

    def _set_detail_enabled(self, enabled: bool) -> None:
        self._tabs.setEnabled(enabled)
        self._watchlist_button.setEnabled(enabled)
        self._analysis_button.setEnabled(enabled)
        self._export_button.setEnabled(enabled)

    def _on_tab_changed(self, index: int) -> None:
        if index != 0:
            self._memo_view.flush_if_dirty()

    def _stock_item_from_row(self, row: StockNoteIndexRow) -> StockItem | None:
        try:
            exchange = Exchange[row.exchange]
        except KeyError:
            return None
        return StockItem(symbol=row.symbol, exchange=exchange, name=row.name)

    def _format_journal_body(self, body: str, row: StockNoteIndexRow) -> str:
        text = body.strip()
        if not text or not self._journal_view.attach_quote_enabled():
            return text
        item = self._stock_item_from_row(row)
        if item is None:
            return text
        quote_line = build_quote_snapshot_for_item(item)
        if not quote_line:
            return text
        return f"[{quote_line}] {text}"

    def _on_entry_submitted(self, body: str) -> None:
        service = self._note_service()
        row = self._current_row
        if service is None or row is None:
            return
        try:
            exchange = Exchange[row.exchange]
        except KeyError:
            return
        final_body = self._format_journal_body(body, row)
        entry = service.append_entry(row.symbol, exchange, final_body)
        if entry is None:
            return
        self._journal_view.prepend_entry(entry)
        self._refresh_row_preview(row.symbol, row.exchange)

    def _on_ai_polish_journal(self) -> None:
        row = self._current_row
        if row is None:
            page_notify(self, "请先选择标的", level="warning")
            return
        raw = self._journal_view.input_text().strip()
        if not raw:
            page_notify(self, "请先输入观察内容", level="info")
            return
        config = get_llm_config(self._main_engine)
        if config is None:
            page_notify(self, "请先在 .env 配置 LLM_API_KEY", level="warning")
            return
        quote_line = ""
        if self._journal_view.attach_quote_enabled():
            item = self._stock_item_from_row(row)
            if item is not None:
                quote_line = build_quote_snapshot_for_item(item)
        messages = build_journal_polish_messages(
            raw,
            vt_symbol=row.vt_symbol,
            name=row.name,
            quote_line=quote_line,
        )
        self._start_ai_worker(
            config,
            messages,
            on_ok=self._on_ai_polish_done,
            journal_busy=True,
        )

    def _on_ai_polish_done(self, text: str) -> None:
        self._journal_view.set_ai_busy(False)
        if not text.strip():
            page_notify(self, "AI 未返回内容", level="warning")
            return
        self._journal_view.set_input_text(text.strip())
        page_notify(self, "已整理，确认后点添加或 Ctrl+Enter", level="success")

    def _on_ai_expand_memo(self) -> None:
        row = self._current_row
        if row is None:
            page_notify(self, "请先选择标的", level="warning")
            return
        full_body = self._memo_view.current_body()
        selection = self._memo_view.selected_text()
        if not full_body.strip() and not selection.strip():
            page_notify(self, "备忘内容为空", level="info")
            return
        config = get_llm_config(self._main_engine)
        if config is None:
            page_notify(self, "请先在 .env 配置 LLM_API_KEY", level="warning")
            return
        try:
            messages = build_memo_expand_messages(
                full_body,
                selection,
                vt_symbol=row.vt_symbol,
                name=row.name,
            )
        except ValueError as ex:
            page_notify(self, str(ex), level="warning")
            return
        self._start_ai_worker(
            config,
            messages,
            on_ok=lambda text: self._on_ai_expand_done(text, full_body, selection),
            memo_busy=True,
        )

    def _on_ai_expand_done(self, expanded: str, full_body: str, selection: str) -> None:
        self._memo_view.set_ai_busy(False)
        if not expanded.strip():
            page_notify(self, "AI 未返回内容", level="warning")
            return
        new_body = apply_expanded_memo(full_body, selection, expanded.strip())
        self._memo_view.replace_memo_body(new_body)
        page_notify(self, "已扩写，将自动保存", level="success")

    def _start_ai_worker(
        self,
        config,
        messages: list[dict[str, str]],
        *,
        on_ok,
        journal_busy: bool = False,
        memo_busy: bool = False,
    ) -> None:
        if self._ai_worker is not None and self._ai_worker.isRunning():
            page_notify(self, "AI 任务进行中", level="info")
            return
        if journal_busy:
            self._journal_view.set_ai_busy(True)
        if memo_busy:
            self._memo_view.set_ai_busy(True)
        worker = NoteAiWorker(config, messages, parent=self)
        self._ai_worker = worker
        worker.finished_ok.connect(on_ok)
        worker.failed.connect(self._on_ai_failed)
        worker.finished.connect(lambda: self._release_ai_worker(worker))
        worker.start()

    def _on_ai_failed(self, message: str) -> None:
        self._journal_view.set_ai_busy(False)
        self._memo_view.set_ai_busy(False)
        page_notify(self, message, level="error")

    def _release_ai_worker(self, worker: NoteAiWorker) -> None:
        if self._ai_worker is worker:
            self._ai_worker = None
        release_thread(self._retired_workers, worker, timeout_ms=500)

    def _on_memo_changed(self) -> None:
        service = self._note_service()
        row = self._current_row
        if service is None or row is None:
            self._memo_view.mark_saved(failed=True)
            return
        try:
            exchange = Exchange[row.exchange]
        except KeyError:
            self._memo_view.mark_saved(failed=True)
            return
        try:
            service.upsert_memo(row.symbol, exchange, self._memo_view.current_body())
            self._memo_view.mark_saved()
            self._refresh_row_preview(row.symbol, row.exchange)
        except Exception:
            self._memo_view.mark_saved(failed=True)

    def _on_entry_delete(self, entry_id: int) -> None:
        service = self._note_service()
        if service is None:
            return
        if not service.delete_entry(entry_id):
            return
        self._journal_view.remove_entry_id(entry_id)
        row = self._current_row
        if row is not None:
            self._refresh_row_preview(row.symbol, row.exchange)

    def _on_report_delete(self, report_id: int) -> None:
        service = self._note_service()
        if service is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "删除报告",
            "确定删除该分析报告？此操作不可恢复。",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if not service.delete_report(report_id):
            return
        self._reports_view.remove_report_id(report_id)
        row = self._current_row
        if row is not None:
            self._refresh_row_preview(row.symbol, row.exchange)

    def _refresh_row_preview(self, symbol: str, exchange_name: str) -> None:
        service = self._note_service()
        if service is None:
            return
        self._rows = service.list_index_rows()
        updated = next(
            (item for item in self._rows if item.symbol == symbol and item.exchange == exchange_name),
            None,
        )
        if updated is not None:
            self._current_row = updated
        current_item = self._symbol_list.currentItem()
        if current_item is not None and updated is not None:
            current_item.setText(_format_symbol_item(updated))
            current_item.setToolTip(updated.memo_preview or f"{updated.entry_count} 条流水")

    def _open_in_watchlist(self) -> None:
        row = self._current_row
        if row is None or self._focus_watchlist is None:
            return
        self._focus_watchlist(row.symbol, row.exchange)

    def _open_stock_analysis(self) -> None:
        row = self._current_row
        if row is None:
            return
        host = StockAnalysisHost.from_main_engine(
            self._main_engine,
            event_engine=self._event_engine,
            source_page="笔记中心",
        )
        show_stock_analysis_vt_symbol(
            row.vt_symbol,
            host,
            name=row.name,
            parent=self,
        )

    def _export_current(self) -> None:
        row = self._current_row
        service = self._note_service()
        if row is None or service is None:
            return
        try:
            exchange = Exchange[row.exchange]
        except KeyError:
            return
        self._memo_view.flush_if_dirty()
        out_dir = BACKUP_DIR / "notes"
        path = service.export_symbol_markdown(
            row.symbol,
            exchange,
            out_dir,
            name=row.name,
        )
        if path is None:
            page_notify(self, "当前标的无笔记内容可导出", level="info")
            return
        page_notify(self, f"已导出 → {path}", level="success")


def _format_symbol_item(row: StockNoteIndexRow) -> str:
    name = row.name.strip()
    head = f"{row.symbol} {name}".strip() if name else row.symbol
    bits: list[str] = []
    if row.has_memo and row.memo_preview:
        bits.append(row.memo_preview)
    if row.entry_count > 0:
        bits.append(f"{row.entry_count} 条流水")
    if row.report_count > 0:
        bits.append(f"{row.report_count} 篇报告")
    suffix = " · ".join(bits)
    return f"{head}\n{suffix}" if suffix else head
