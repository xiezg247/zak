"""自选页个股笔记联动。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class StockNotesFeature:
    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def wire_panel(self) -> None:
        panel = getattr(self._page, "stock_note_panel", None)
        if panel is None:
            return
        panel.notes_changed.connect(self._on_notes_changed)
        panel.expansion_changed.connect(self._on_expansion_changed)

    def on_selection_item(self) -> None:
        page = self._page
        panel = getattr(page, "stock_note_panel", None)
        if panel is None:
            return
        panel.bind_item(page.current_item)

    def focus_quick_note(self) -> None:
        panel = getattr(self._page, "stock_note_panel", None)
        if panel is None:
            return
        panel.focus_for_quick_note()

    def _on_notes_changed(self) -> None:
        self._page._actions.emit_ai_context()

    def _on_expansion_changed(self, _expanded: bool) -> None:
        pass
