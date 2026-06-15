"""自选/本地页中部纵向 Splitter（主表、信号区、持仓区、运行输出）尺寸同步。"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
    load_center_splitter_sizes,
    load_signal_panel_expanded,
    save_center_splitter_sizes,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

SIGNAL_PANEL_DEFAULT_HEIGHT = 240
SIGNAL_PANEL_COLLAPSED_HEIGHT = 32
POSITION_PANEL_DEFAULT_HEIGHT = 220
POSITION_PANEL_COLLAPSED_HEIGHT = 32
RUN_OUTPUT_EXPANDED_HEIGHT = 160
RUN_OUTPUT_COLLAPSED_HEIGHT = 32
TABLE_MIN_HEIGHT = 160


def center_splitter(page: QuotesPage) -> QtWidgets.QSplitter | None:
    splitter = getattr(page, "_center_splitter", None)
    if isinstance(splitter, QtWidgets.QSplitter):
        return splitter
    fallback = getattr(page, "_run_output_splitter", None)
    return cast(QtWidgets.QSplitter | None, fallback)


def _table_host(page: QuotesPage):
    return getattr(page, "_market_table_host", None)


def _signal_panel(page: QuotesPage):
    return getattr(page, "signal_panel", None)


def _position_panel(page: QuotesPage):
    return getattr(page, "position_panel", None)


def _run_output_panel(page: QuotesPage):
    from vnpy_ashare.ui.quotes.page.run_log import run_output_panel

    return run_output_panel(page)


def compute_center_splitter_sizes(
    total_height: int,
    *,
    has_signal_panel: bool,
    signal_expanded: bool,
    has_position_panel: bool,
    position_expanded: bool,
    has_run_output: bool,
    run_expanded: bool,
    signal_min_height: int = 0,
    position_min_height: int = 0,
    run_min_height: int = 0,
) -> dict[str, int]:
    """计算主表与各面板的像素高度。"""
    total = max(int(total_height), 360)
    signal_h = 0
    if has_signal_panel:
        signal_h = SIGNAL_PANEL_DEFAULT_HEIGHT if signal_expanded else SIGNAL_PANEL_COLLAPSED_HEIGHT
        if signal_min_height > 0 and signal_expanded:
            signal_h = max(signal_h, signal_min_height)
    position_h = 0
    if has_position_panel:
        position_h = POSITION_PANEL_DEFAULT_HEIGHT if position_expanded else POSITION_PANEL_COLLAPSED_HEIGHT
        if position_min_height > 0 and position_expanded:
            position_h = max(position_h, position_min_height)
    run_h = 0
    if has_run_output:
        run_h = RUN_OUTPUT_EXPANDED_HEIGHT if run_expanded else RUN_OUTPUT_COLLAPSED_HEIGHT
        if run_min_height > 0 and run_expanded:
            run_h = max(run_h, run_min_height)
    table_h = max(total - signal_h - position_h - run_h, TABLE_MIN_HEIGHT)
    return {
        "table": table_h,
        "signal": signal_h,
        "position": position_h,
        "run": run_h,
    }


def configure_center_splitter(splitter: QtWidgets.QSplitter) -> None:
    """子面板固定高度，余量全部给主表。"""
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(6)
    for index in range(splitter.count()):
        splitter.setStretchFactor(index, 1 if index == 0 else 0)


def _panel_min_splitter_height(
    panel,
    *,
    default_height: int,
    collapsed_height: int,
) -> int:
    """面板在 splitter 中应占的最小高度（展开取默认/控件最小高度，折叠取折叠高度）。"""
    if panel is None:
        return 0
    expanded = panel.is_expanded() if hasattr(panel, "is_expanded") else True
    if expanded:
        widget_min = panel.minimumHeight() if hasattr(panel, "minimumHeight") else default_height
        return max(default_height, widget_min)
    return collapsed_height


def _migrate_saved_sizes(page: QuotesPage, splitter: QtWidgets.QSplitter, saved: list[int]) -> list[int]:
    """兼容旧版 splitter 段数（如仅主表+信号区、或运行输出区替换为持仓区）。"""
    if not saved:
        return []
    count = splitter.count()
    position_panel = _position_panel(page)
    run_panel = _run_output_panel(page)

    if len(saved) == 2 and count == 3 and position_panel is not None:
        pos_h = _panel_min_splitter_height(
            position_panel,
            default_height=POSITION_PANEL_DEFAULT_HEIGHT,
            collapsed_height=POSITION_PANEL_COLLAPSED_HEIGHT,
        )
        return [saved[0], saved[1], pos_h]

    if len(saved) == 3 and count == 3 and run_panel is None and position_panel is not None:
        pos_h = _panel_min_splitter_height(
            position_panel,
            default_height=POSITION_PANEL_DEFAULT_HEIGHT,
            collapsed_height=POSITION_PANEL_COLLAPSED_HEIGHT,
        )
        return [saved[0], saved[1], pos_h]

    if len(saved) != count:
        return []
    return list(saved)


def _normalize_saved_sizes(page: QuotesPage, splitter: QtWidgets.QSplitter, saved: list[int]) -> list[int]:
    """按各面板展开状态校正保存高度，避免展开态却只有折叠像素导致内容被裁切。"""
    if len(saved) != splitter.count():
        return []

    signal_panel = _signal_panel(page)
    position_panel = _position_panel(page)
    run_panel = _run_output_panel(page)
    result = list(saved)

    for index in range(splitter.count()):
        widget = splitter.widget(index)
        if widget is signal_panel:
            min_h = _panel_min_splitter_height(
                signal_panel,
                default_height=SIGNAL_PANEL_DEFAULT_HEIGHT,
                collapsed_height=SIGNAL_PANEL_COLLAPSED_HEIGHT,
            )
            if signal_panel.is_expanded():
                result[index] = max(result[index], min_h)
            else:
                result[index] = SIGNAL_PANEL_COLLAPSED_HEIGHT
        elif widget is position_panel:
            min_h = _panel_min_splitter_height(
                position_panel,
                default_height=POSITION_PANEL_DEFAULT_HEIGHT,
                collapsed_height=POSITION_PANEL_COLLAPSED_HEIGHT,
            )
            if position_panel.is_expanded():
                result[index] = max(result[index], min_h)
            else:
                result[index] = POSITION_PANEL_COLLAPSED_HEIGHT
        elif widget is run_panel:
            min_h = _panel_min_splitter_height(
                run_panel,
                default_height=RUN_OUTPUT_EXPANDED_HEIGHT,
                collapsed_height=RUN_OUTPUT_COLLAPSED_HEIGHT,
            )
            if run_panel.is_expanded():
                result[index] = max(result[index], min_h)
            else:
                result[index] = RUN_OUTPUT_COLLAPSED_HEIGHT

    total = max(splitter.height(), sum(splitter.sizes()), 400)
    if len(result) > 1:
        result[0] = max(total - sum(result[1:]), TABLE_MIN_HEIGHT)
    extra = sum(result) - total
    if extra > 0 and result[0] > TABLE_MIN_HEIGHT:
        result[0] = max(TABLE_MIN_HEIGHT, result[0] - extra)
    elif sum(result) < total:
        result[0] += total - sum(result)
    return result


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
    position_panel = _position_panel(page)
    run_panel = _run_output_panel(page)

    sizes_map = compute_center_splitter_sizes(
        max(splitter.height(), sum(splitter.sizes()), 400),
        has_signal_panel=signal_panel is not None,
        signal_expanded=signal_panel.is_expanded() if signal_panel is not None else False,
        has_position_panel=position_panel is not None,
        position_expanded=position_panel.is_expanded() if position_panel is not None else False,
        has_run_output=run_panel is not None,
        run_expanded=run_panel.is_expanded() if run_panel is not None else False,
        signal_min_height=signal_panel.minimumHeight() if signal_panel is not None else 0,
        position_min_height=position_panel.minimumHeight() if position_panel is not None else 0,
        run_min_height=run_panel.minimumHeight() if run_panel is not None else 0,
    )

    new_sizes: list[int] = []
    for index in range(splitter.count()):
        widget = splitter.widget(index)
        if widget is table_host:
            new_sizes.append(sizes_map["table"])
        elif widget is signal_panel:
            new_sizes.append(sizes_map["signal"])
        elif widget is position_panel:
            new_sizes.append(sizes_map["position"])
        elif widget is run_panel:
            new_sizes.append(sizes_map["run"])
        else:
            current = splitter.sizes()
            new_sizes.append(current[index] if index < len(current) else 0)

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
    position_panel = _position_panel(page)
    if position_panel is not None:
        from vnpy_ashare.ui.quotes.watchlist_positions.settings import load_position_panel_expanded

        position_panel.set_expanded(load_position_panel_expanded(), emit=False)
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
    saved = _migrate_saved_sizes(page, splitter, load_center_splitter_sizes())
    if saved:
        normalized = _normalize_saved_sizes(page, splitter, saved)
        if normalized and sum(normalized) >= 320:
            splitter.blockSignals(True)
            splitter.setSizes(normalized)
            splitter.blockSignals(False)
            if signal_panel is not None:
                signal_panel.render_panel()
            if position_panel is not None:
                position_panel.render_panel()
            return
    apply_center_splitter_sizes(page)
    if signal_panel is not None:
        signal_panel.render_panel()
    if position_panel is not None:
        position_panel.render_panel()


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
