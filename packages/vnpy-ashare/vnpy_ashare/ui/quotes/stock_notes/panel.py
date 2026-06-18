"""个股笔记 Panel：备忘 + 流水。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.stock_notes import (
    TAB_ENTRY,
    TAB_MEMO,
    load_stock_note_active_tab,
    load_stock_note_panel_expanded,
    load_stock_note_quick_tab,
    save_stock_note_active_tab,
    save_stock_note_panel_expanded,
)
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.trading.journal.import_from_note import import_stock_note_by_id
from vnpy_ashare.ui.quotes.stock_notes.ai_assist import (
    NoteAiWorker,
    apply_expanded_memo,
    build_journal_polish_messages,
    build_memo_expand_messages,
    build_quote_snapshot_line,
    get_llm_config,
)
from vnpy_ashare.ui.quotes.stock_notes.journal_tab import StockNoteJournalTab
from vnpy_ashare.ui.quotes.stock_notes.memo_tab import StockNoteMemoTab
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class StockNotePanel(QtWidgets.QWidget):
    expansion_changed = QtCore.Signal(bool)
    notes_changed = QtCore.Signal()

    def __init__(self, page: QuotesPage) -> None:
        super().__init__(page)
        self._page = page
        self._bound_symbol: str | None = None
        self._bound_exchange: Exchange | None = None
        self._bound_name: str = ""
        self._expanded = load_stock_note_panel_expanded()
        self._ai_worker: NoteAiWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []

        self.setObjectName("StockNotePanel")
        theme_manager().bind_stylesheet(self)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self._collapse_button = QtWidgets.QToolButton(self)
        self._collapse_button.setCheckable(True)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)
        header.addWidget(self._collapse_button)

        title = QtWidgets.QLabel("笔记", self)
        title.setObjectName("StockNoteTitle")
        header.addWidget(title)
        header.addStretch()

        self._clear_button = QtWidgets.QPushButton("清空", self)
        self._clear_button.setObjectName("SecondaryButton")
        self._clear_button.clicked.connect(self._on_clear_clicked)
        header.addWidget(self._clear_button)

        self._memo_tab = StockNoteMemoTab(self)
        self._journal_tab = StockNoteJournalTab(self)
        self._tabs = QtWidgets.QTabWidget(self)
        self._tabs.setObjectName("StockNoteTabs")
        self._tabs.addTab(self._memo_tab, "备忘")
        self._tabs.addTab(self._journal_tab, "流水")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(4)
        root.addLayout(header)
        root.addWidget(self._tabs, stretch=1)

        self._memo_tab.memo_changed.connect(self._on_memo_changed)
        self._memo_tab.ai_expand_requested.connect(self._on_ai_expand_memo)
        self._journal_tab.entry_submitted.connect(self._on_entry_submitted)
        self._journal_tab.entry_delete_requested.connect(self._on_entry_delete_requested)
        self._journal_tab.entry_import_requested.connect(self._on_entry_import_requested)
        self._journal_tab.ai_polish_requested.connect(self._on_ai_polish_journal)

        active_tab = load_stock_note_active_tab()
        self._tabs.setCurrentIndex(0 if active_tab == TAB_MEMO else 1)
        self.set_expanded(self._expanded, emit=False)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        changed = self._expanded != expanded
        self._expanded = expanded
        self._sync_collapse_button()
        self._tabs.setVisible(expanded)
        if expanded:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(140)
        else:
            self.setMinimumHeight(28)
            self.setMaximumHeight(36)
        if emit and changed:
            save_stock_note_panel_expanded(expanded)
            self.expansion_changed.emit(expanded)

    def expand(self) -> None:
        self.set_expanded(True)

    def bind_item(self, item: StockItem | None) -> None:
        self._flush_memo()
        if item is None:
            self._bound_symbol = None
            self._bound_exchange = None
            self._bound_name = ""
            self._memo_tab.clear()
            self._journal_tab.clear()
            return

        self._bound_symbol = item.symbol
        self._bound_exchange = item.exchange
        self._bound_name = item.name
        service = self._page._get_note_service()
        if service is None:
            self._memo_tab.clear()
            self._journal_tab.clear()
            return

        bundle = service.get_bundle(item.symbol, item.exchange)
        memo_body = bundle.memo.body if bundle.memo is not None else ""
        self._memo_tab.load_body(memo_body)
        self._journal_tab.load_entries(bundle.entries)

    def flush_memo(self) -> None:
        self._flush_memo()

    def focus_for_quick_note(self) -> None:
        self.expand()

        tab = load_stock_note_quick_tab()
        if tab == TAB_MEMO:
            self._tabs.setCurrentIndex(0)
            self._memo_tab.focus_editor()
        else:
            self._tabs.setCurrentIndex(1)
            self._journal_tab.focus_input()

    def _on_collapse_toggled(self, expanded: bool) -> None:
        self.set_expanded(expanded)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        arrow = QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow
        self._collapse_button.setArrowType(arrow)
        self._collapse_button.blockSignals(False)

    def _on_tab_changed(self, index: int) -> None:
        save_stock_note_active_tab(TAB_MEMO if index == 0 else TAB_ENTRY)
        if index != 0:
            self._memo_tab.flush_if_dirty()

    def _on_memo_changed(self) -> None:
        service = self._page._get_note_service()
        if service is None or self._bound_symbol is None or self._bound_exchange is None:
            self._memo_tab.mark_saved(failed=True)
            return
        try:
            service.upsert_memo(
                self._bound_symbol,
                self._bound_exchange,
                self._memo_tab.current_body(),
            )
            self._memo_tab.mark_saved()
            self.notes_changed.emit()
        except Exception:
            self._memo_tab.mark_saved(failed=True)

    def _on_entry_submitted(self, body: str) -> None:
        service = self._page._get_note_service()
        if service is None or self._bound_symbol is None or self._bound_exchange is None:
            return
        final_body = self._format_journal_body(body)
        entry = service.append_entry(self._bound_symbol, self._bound_exchange, final_body)
        if entry is None:
            return
        self._journal_tab.prepend_entry(entry)
        self.notes_changed.emit()

    def _format_journal_body(self, body: str) -> str:
        text = body.strip()
        if not text or not self._journal_tab.attach_quote_enabled():
            return text
        item = self._page.current_item
        if item is None:
            return text
        quote_line = build_quote_snapshot_line(self._page, item)
        if not quote_line:
            return text
        return f"[{quote_line}] {text}"

    def _on_ai_polish_journal(self) -> None:
        raw = self._journal_tab.input_text().strip()
        if not raw:
            page_notify(self, "请先输入观察内容", level="info")
            return
        if self._bound_symbol is None or self._bound_exchange is None:
            page_notify(self, "未绑定标的", level="warning")
            return
        config = get_llm_config(self._page._get_main_engine())
        if config is None:
            page_notify(self, "请先在 .env 配置 LLM_API_KEY", level="warning")
            return
        item = self._page.current_item
        quote_line = ""
        if item is not None and self._journal_tab.attach_quote_enabled():
            quote_line = build_quote_snapshot_line(self._page, item)
        vt_symbol = f"{self._bound_symbol}.{self._bound_exchange.name}"
        messages = build_journal_polish_messages(
            raw,
            vt_symbol=vt_symbol,
            name=self._bound_name,
            quote_line=quote_line,
        )
        self._start_ai_worker(
            config,
            messages,
            on_ok=self._on_ai_polish_done,
            journal_busy=True,
        )

    def _on_ai_polish_done(self, text: str) -> None:
        self._journal_tab.set_ai_busy(False)
        if not text.strip():
            page_notify(self, "AI 未返回内容", level="warning")
            return
        self._journal_tab.set_input_text(text.strip())
        page_notify(self, "已整理，确认后点添加或 Ctrl+Enter", level="success")

    def _on_ai_expand_memo(self) -> None:
        if self._bound_symbol is None or self._bound_exchange is None:
            page_notify(self, "未绑定标的", level="warning")
            return
        full_body = self._memo_tab.current_body()
        selection = self._memo_tab.selected_text()
        if not full_body.strip() and not selection.strip():
            page_notify(self, "备忘内容为空", level="info")
            return
        config = get_llm_config(self._page._get_main_engine())
        if config is None:
            page_notify(self, "请先在 .env 配置 LLM_API_KEY", level="warning")
            return
        vt_symbol = f"{self._bound_symbol}.{self._bound_exchange.name}"
        try:
            messages = build_memo_expand_messages(
                full_body,
                selection,
                vt_symbol=vt_symbol,
                name=self._bound_name,
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
        self._memo_tab.set_ai_busy(False)
        if not expanded.strip():
            page_notify(self, "AI 未返回内容", level="warning")
            return
        new_body = apply_expanded_memo(full_body, selection, expanded.strip())
        self._memo_tab.replace_memo_body(new_body)
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
            self._journal_tab.set_ai_busy(True)
        if memo_busy:
            self._memo_tab.set_ai_busy(True)
        worker = NoteAiWorker(config, messages, parent=self)
        self._ai_worker = worker
        worker.finished_ok.connect(on_ok)
        worker.failed.connect(self._on_ai_failed)
        worker.finished.connect(lambda: self._release_ai_worker(worker))
        worker.start()

    def _on_ai_failed(self, message: str) -> None:
        self._journal_tab.set_ai_busy(False)
        self._memo_tab.set_ai_busy(False)
        page_notify(self, message, level="error")

    def _release_ai_worker(self, worker: NoteAiWorker) -> None:
        if self._ai_worker is worker:
            self._ai_worker = None
        release_thread(self._retired_workers, worker, timeout_ms=500)

    def _on_entry_delete_requested(self, entry_id: int) -> None:
        service = self._page._get_note_service()
        if service is None:
            return
        if not service.delete_entry(entry_id):
            return
        self._journal_tab.remove_entry_id(entry_id)
        self.notes_changed.emit()

    def _on_entry_import_requested(self, entry_id: int) -> None:
        journal_id = import_stock_note_by_id(entry_id)
        if journal_id is None:
            page_notify(self, "导入失败，请检查笔记内容", level="warning")
            return
        page_notify(self, f"已导入交易流水 #{journal_id}", level="success")

    def _on_clear_clicked(self) -> None:
        if self._bound_symbol is None or self._bound_exchange is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "清空笔记",
            f"确定清空 {self._bound_symbol}.{self._bound_exchange.value} 的全部备忘与流水？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        service = self._page._get_note_service()
        if service is None:
            return
        service.clear_notes(self._bound_symbol, self._bound_exchange)
        self._memo_tab.clear()
        self._journal_tab.clear()
        self.notes_changed.emit()

    def _flush_memo(self) -> None:
        if not self._memo_tab.is_dirty():
            return
        self._on_memo_changed()
