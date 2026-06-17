"""看盘页运行输出面板写入（本地 / 自选等）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.ui.quotes.page.run_output_state import (
    load_run_output_expanded,
    run_output_panel,
    save_run_output_expanded,
)

__all__ = [
    "append_run_log",
    "begin_run_log",
    "collapse_run_output",
    "complete_run_log",
    "expand_run_output",
    "fail_run_log",
    "load_run_output_expanded",
    "on_run_output_expansion_changed",
    "run_output_panel",
    "save_run_output_expanded",
    "sync_run_output_expansion",
]

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def _apply_splitter_sizes(page: QuotesPage, *, expanded: bool) -> None:
    del expanded
    from vnpy_ashare.ui.quotes.watchlist_signals.splitter import apply_center_splitter_sizes

    apply_center_splitter_sizes(page)


def sync_run_output_expansion(
    page: QuotesPage,
    expanded: bool,
    *,
    persist: bool = False,
    adjust_splitter: bool = True,
) -> None:
    panel = run_output_panel(page)
    if panel is None:
        return
    panel.set_expanded(expanded, emit=False)
    if adjust_splitter:
        _apply_splitter_sizes(page, expanded=expanded)
    if persist:
        save_run_output_expanded(page.page_name, expanded)


def collapse_run_output(page: QuotesPage) -> None:
    sync_run_output_expansion(page, False, adjust_splitter=True)


def expand_run_output(page: QuotesPage) -> None:
    sync_run_output_expansion(page, True, adjust_splitter=True)


def on_run_output_expansion_changed(page: QuotesPage, expanded: bool) -> None:
    sync_run_output_expansion(page, expanded, persist=True, adjust_splitter=True)


def append_run_log(page: QuotesPage, message: str) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        if not panel.is_expanded():
            expand_run_output(page)
        panel.append_log(message)


def begin_run_log(page: QuotesPage, title: str) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        expand_run_output(page)
        panel.begin_task(title)


def complete_run_log(page: QuotesPage, summary: str, *, detail: str | None = None) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        panel.complete_task(summary=summary, detail=detail)


def fail_run_log(page: QuotesPage, message: str) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        panel.fail_task(message)
