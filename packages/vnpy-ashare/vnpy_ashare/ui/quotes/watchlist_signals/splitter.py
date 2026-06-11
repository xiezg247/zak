"""自选/本地页中部纵向 Splitter（主表、信号区、运行输出）尺寸同步。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.watchlist_signals.settings import load_signal_panel_expanded

if TYPE_CHECKING:
    from vnpy.trader.ui import QtWidgets

    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

SIGNAL_PANEL_DEFAULT_HEIGHT = 180
SIGNAL_PANEL_COLLAPSED_HEIGHT = 32
RUN_OUTPUT_EXPANDED_HEIGHT = 160
RUN_OUTPUT_COLLAPSED_HEIGHT = 32


def center_splitter(page: QuotesPage) -> QtWidgets.QSplitter | None:
    splitter = getattr(page, "_center_splitter", None)
    if splitter is not None:
        return splitter
    return getattr(page, "_run_output_splitter", None)


def _table_host(page: QuotesPage):
    return getattr(page, "_market_table_host", None)


def _signal_panel(page: QuotesPage):
    return getattr(page, "signal_panel", None)


def _run_output_panel(page: QuotesPage):
    from vnpy_ashare.ui.quotes.page.run_log import run_output_panel

    return run_output_panel(page)


def _widget_height(widget, *, expanded: bool, expanded_height: int, collapsed_height: int) -> int:
    if not expanded:
        return collapsed_height
    return max(expanded_height, widget.minimumHeight())


def apply_center_splitter_sizes(page: QuotesPage, *, _retry: int = 0) -> None:
    splitter = center_splitter(page)
    if splitter is None:
        return

    if splitter.height() < 120 and _retry < 10:
        QtCore.QTimer.singleShot(
            50,
            lambda: apply_center_splitter_sizes(page, _retry=_retry + 1),
        )
        return

    table_host = _table_host(page)
    signal_panel = _signal_panel(page)
    run_panel = _run_output_panel(page)

    sizes = splitter.sizes()
    total = max(sum(sizes), splitter.height(), 400)

    signal_h = 0
    run_h = 0
    if signal_panel is not None and signal_panel.parent() is splitter:
        signal_h = _widget_height(
            signal_panel,
            expanded=signal_panel.is_expanded(),
            expanded_height=SIGNAL_PANEL_DEFAULT_HEIGHT,
            collapsed_height=SIGNAL_PANEL_COLLAPSED_HEIGHT,
        )
    if run_panel is not None and run_panel.parent() is splitter:
        run_h = _widget_height(
            run_panel,
            expanded=run_panel.is_expanded(),
            expanded_height=RUN_OUTPUT_EXPANDED_HEIGHT,
            collapsed_height=RUN_OUTPUT_COLLAPSED_HEIGHT,
        )

    table_h = max(total - signal_h - run_h, 200)
    new_sizes: list[int] = []
    for index in range(splitter.count()):
        widget = splitter.widget(index)
        if widget is table_host:
            new_sizes.append(table_h)
        elif widget is signal_panel:
            new_sizes.append(signal_h)
        elif widget is run_panel:
            new_sizes.append(run_h)
        else:
            new_sizes.append(sizes[index] if index < len(sizes) else 0)

    if new_sizes:
        splitter.setSizes(new_sizes)


def restore_center_splitter(page: QuotesPage) -> None:
    from vnpy_ashare.ui.quotes.page.run_log import load_run_output_expanded, sync_run_output_expansion

    signal_panel = _signal_panel(page)
    if signal_panel is not None:
        signal_panel.set_expanded(load_signal_panel_expanded(), emit=False)
    run_panel = _run_output_panel(page)
    if run_panel is not None:
        sync_run_output_expansion(
            page,
            load_run_output_expanded(page.page_name),
            adjust_splitter=False,
        )
    apply_center_splitter_sizes(page)
