"""自选/本地页中部纵向 Splitter（主表、信号区、运行输出）尺寸同步。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
    load_center_splitter_sizes,
    load_signal_panel_expanded,
    save_center_splitter_sizes,
)

if TYPE_CHECKING:
    from vnpy.trader.ui import QtWidgets

    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

SIGNAL_PANEL_DEFAULT_HEIGHT = 240
SIGNAL_PANEL_COLLAPSED_HEIGHT = 32
RUN_OUTPUT_EXPANDED_HEIGHT = 160
RUN_OUTPUT_COLLAPSED_HEIGHT = 32
TABLE_MIN_HEIGHT = 160


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


def compute_center_splitter_sizes(
    total_height: int,
    *,
    signal_expanded: bool,
    run_expanded: bool,
    signal_min_height: int = 0,
    run_min_height: int = 0,
) -> tuple[int, int, int]:
    """计算主表 / 信号区 / 运行输出的像素高度。"""
    total = max(int(total_height), 320)
    signal_h = SIGNAL_PANEL_DEFAULT_HEIGHT if signal_expanded else SIGNAL_PANEL_COLLAPSED_HEIGHT
    if signal_min_height > 0 and signal_expanded:
        signal_h = max(signal_h, signal_min_height)
    run_h = RUN_OUTPUT_EXPANDED_HEIGHT if run_expanded else RUN_OUTPUT_COLLAPSED_HEIGHT
    if run_min_height > 0 and run_expanded:
        run_h = max(run_h, run_min_height)
    table_h = max(total - signal_h - run_h, TABLE_MIN_HEIGHT)
    return table_h, signal_h, run_h


def configure_center_splitter(splitter: QtWidgets.QSplitter) -> None:
    """信号区 / 运行输出固定高度，余量全部给主表。"""
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(6)
    for index in range(splitter.count()):
        splitter.setStretchFactor(index, 1 if index == 0 else 0)


def apply_center_splitter_sizes(page: QuotesPage, *, _retry: int = 0) -> None:
    splitter = center_splitter(page)
    if splitter is None:
        return

    if splitter.height() < 120 and _retry < 12:
        QtCore.QTimer.singleShot(
            50,
            lambda: apply_center_splitter_sizes(page, _retry=_retry + 1),
        )
        return

    configure_center_splitter(splitter)

    table_host = _table_host(page)
    signal_panel = _signal_panel(page)
    run_panel = _run_output_panel(page)

    signal_expanded = signal_panel.is_expanded() if signal_panel is not None else False
    run_expanded = run_panel.is_expanded() if run_panel is not None else False
    signal_min = signal_panel.minimumHeight() if signal_panel is not None else 0
    run_min = run_panel.minimumHeight() if run_panel is not None else 0

    total = max(splitter.height(), sum(splitter.sizes()), 400)
    table_h, signal_h, run_h = compute_center_splitter_sizes(
        total,
        signal_expanded=signal_expanded,
        run_expanded=run_expanded,
        signal_min_height=signal_min,
        run_min_height=run_min,
    )

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
            sizes = splitter.sizes()
            new_sizes.append(sizes[index] if index < len(sizes) else 0)

    if not new_sizes:
        return

    splitter.blockSignals(True)
    splitter.setSizes(new_sizes)
    splitter.blockSignals(False)


def restore_center_splitter(page: QuotesPage) -> None:
    from vnpy_ashare.ui.quotes.page.run_log import load_run_output_expanded, sync_run_output_expansion

    signal_panel = _signal_panel(page)
    if signal_panel is not None:
        signal_panel.set_expanded(load_signal_panel_expanded(), emit=False)
        if hasattr(signal_panel, "sync_splitter_geometry"):
            signal_panel.sync_splitter_geometry()
    run_panel = _run_output_panel(page)
    if run_panel is not None:
        sync_run_output_expansion(
            page,
            load_run_output_expanded(page.page_name),
            adjust_splitter=False,
        )

    splitter = center_splitter(page)
    if splitter is None:
        return

    configure_center_splitter(splitter)
    saved = load_center_splitter_sizes()
    height = max(splitter.height(), sum(splitter.sizes()), 400)
    signal_panel = _signal_panel(page)
    signal_index = None
    if signal_panel is not None:
        for index in range(splitter.count()):
            if splitter.widget(index) is signal_panel:
                signal_index = index
                break
    if (
        saved
        and signal_index is not None
        and signal_panel is not None
        and signal_panel.is_expanded()
        and len(saved) == splitter.count()
        and saved[signal_index] < SIGNAL_PANEL_DEFAULT_HEIGHT - 20
    ):
        saved = []
    if saved and len(saved) == splitter.count() and sum(saved) >= 320 and abs(sum(saved) - height) <= max(24, height // 10):
        splitter.blockSignals(True)
        splitter.setSizes(saved)
        splitter.blockSignals(False)
        return
    apply_center_splitter_sizes(page)


def bind_center_splitter_persistence(page: QuotesPage) -> None:
    """用户拖动分隔条时保存尺寸。"""
    splitter = center_splitter(page)
    if splitter is None:
        return
    if getattr(page, "_center_splitter_bound", False):
        return
    page._center_splitter_bound = True

    def _on_moved(_pos: int, _index: int) -> None:
        save_center_splitter_sizes(splitter.sizes())

    splitter.splitterMoved.connect(_on_moved)
