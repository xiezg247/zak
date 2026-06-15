"""QSplitter 尺寸设置与持久化通用工具。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy.trader.ui import QtWidgets


def splitter_total_height(splitter: QtWidgets.QSplitter, *, min_total: int = 400) -> int:
    return max(splitter.height(), sum(splitter.sizes()), min_total)


def splitter_total_width(splitter: QtWidgets.QSplitter, *, min_total: int = 200) -> int:
    width = splitter.width()
    if width > 0:
        return width
    return max(sum(splitter.sizes()), min_total)


def set_splitter_sizes_quiet(splitter: QtWidgets.QSplitter, sizes: list[int]) -> None:
    splitter.blockSignals(True)
    splitter.setSizes(sizes)
    splitter.blockSignals(False)


def clamp_primary_sizes(
    sizes: list[int],
    *,
    total: int,
    primary_min: int,
    primary_index: int = 0,
) -> list[int]:
    """校正 sizes 总和与 total，余量归 primary 段（通常为表格/主区）。"""
    if len(sizes) <= 1:
        return list(sizes)
    result = list(sizes)
    result[primary_index] = max(total - sum(result[primary_index + 1:]), primary_min)
    extra = sum(result) - total
    if extra > 0 and result[primary_index] > primary_min:
        result[primary_index] = max(primary_min, result[primary_index] - extra)
    elif sum(result) < total:
        result[primary_index] += total - sum(result)
    return result


def panel_min_splitter_height(
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


def panel_slot_height(
    present: bool,
    expanded: bool,
    default_height: int,
    collapsed_height: int,
    min_height: int = 0,
) -> int:
    """计算 splitter 中某段面板的像素高度（不存在则为 0）。"""
    if not present:
        return 0
    if not expanded:
        return collapsed_height
    height = default_height
    if min_height > 0:
        height = max(height, min_height)
    return height


def bind_splitter_persistence(
    splitter: QtWidgets.QSplitter,
    save_fn: Callable[[list[int]], None],
    *,
    bound_flag: str | None = None,
    host: object | None = None,
) -> bool:
    """绑定 splitterMoved 持久化；若 host 上 bound_flag 已为 True 则跳过。"""
    if host is not None and bound_flag and getattr(host, bound_flag, False):
        return False
    if host is not None and bound_flag:
        setattr(host, bound_flag, True)

    def _on_moved(_pos: int, _index: int) -> None:
        save_fn(list(splitter.sizes()))

    splitter.splitterMoved.connect(_on_moved)
    return True
