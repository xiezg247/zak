"""看盘页运行输出面板写入（本地 / 自选等）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

if TYPE_CHECKING:
    from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

_RUN_OUTPUT_EXPANDED_KEY = "quotes/run_output/{page_name}/expanded"


def run_output_panel(page: QuotesPage) -> TaskRunOutputPanel | None:
    if not page.config.show_run_output_panel:
        return None
    panel = getattr(page, "run_output_panel", None)
    return panel


def _settings() -> QtCore.QSettings:
    return QtCore.QSettings("vnpy_ashare", "ZakTerminal")


def _coerce_settings_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_run_output_expanded(page_name: str) -> bool:
    settings = _settings()
    return _coerce_settings_bool(
        settings.value(_RUN_OUTPUT_EXPANDED_KEY.format(page_name=page_name)),
        default=False,
    )


def save_run_output_expanded(page_name: str, expanded: bool) -> None:
    settings = _settings()
    settings.setValue(_RUN_OUTPUT_EXPANDED_KEY.format(page_name=page_name), expanded)


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
