"""自选/本地页中部纵向 Splitter（主表、信号区、持仓区、运行输出）尺寸同步。"""

from __future__ import annotations

from pydantic import Field
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.watchlist_position import load_position_panel_expanded
from vnpy_ashare.config.preferences.watchlist_signal import load_center_splitter_sizes, load_signal_panel_expanded, save_center_splitter_sizes
from vnpy_ashare.ui.components.splitter_utils import (
    bind_splitter_persistence,
    clamp_primary_sizes,
    panel_min_splitter_height,
    panel_slot_height,
    set_splitter_sizes_quiet,
    splitter_total_height,
)
from vnpy_ashare.ui.quotes.page.run_log import sync_run_output_expansion
from vnpy_ashare.ui.quotes.page.run_output_state import load_run_output_expanded, run_output_panel
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_common.domain.base import FrozenModel

SIGNAL_PANEL_DEFAULT_HEIGHT = 240
SIGNAL_PANEL_COLLAPSED_HEIGHT = 32
POSITION_PANEL_DEFAULT_HEIGHT = 220
POSITION_PANEL_COLLAPSED_HEIGHT = 32
RUN_OUTPUT_EXPANDED_HEIGHT = 160
RUN_OUTPUT_COLLAPSED_HEIGHT = 32
TABLE_MIN_HEIGHT = 160


class _CenterPanelSpec(FrozenModel):
    key: str = Field(description="键名")
    default_height: int = Field(description="展开时默认高度")
    collapsed_height: int = Field(description="折叠时高度")


_CENTER_PANEL_SPECS: tuple[_CenterPanelSpec, ...] = (
    _CenterPanelSpec(key="signal", default_height=SIGNAL_PANEL_DEFAULT_HEIGHT, collapsed_height=SIGNAL_PANEL_COLLAPSED_HEIGHT),
    _CenterPanelSpec(key="position", default_height=POSITION_PANEL_DEFAULT_HEIGHT, collapsed_height=POSITION_PANEL_COLLAPSED_HEIGHT),
    _CenterPanelSpec(key="run", default_height=RUN_OUTPUT_EXPANDED_HEIGHT, collapsed_height=RUN_OUTPUT_COLLAPSED_HEIGHT),
)


def _panel_is_expanded(panel: QtWidgets.QWidget) -> bool:
    expanded_fn = getattr(panel, "is_expanded", None)
    if callable(expanded_fn):
        return bool(expanded_fn())
    return True


def center_splitter(page: WatchlistHost) -> QtWidgets.QSplitter | None:
    splitter = page._center_splitter
    if isinstance(splitter, QtWidgets.QSplitter):
        return splitter
    return None


def _run_output_panel(page: WatchlistHost) -> QtWidgets.QWidget | None:

    return run_output_panel(page)


def _center_panel_widgets(page: WatchlistHost) -> dict[str, QtWidgets.QWidget | None]:
    return {
        "table": page._market_table_host,
        "signal": page.signal_panel,
        "position": page.position_panel,
        "run": _run_output_panel(page),
    }


def _center_panel_by_widget(page: WatchlistHost) -> dict[QtWidgets.QWidget, _CenterPanelSpec]:
    widgets = _center_panel_widgets(page)
    mapping: dict[QtWidgets.QWidget, _CenterPanelSpec] = {}
    for spec in _CENTER_PANEL_SPECS:
        widget = widgets.get(spec.key)
        if widget is not None:
            mapping[widget] = spec
    return mapping


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
    table_ratio: float | None = None,
) -> dict[str, int]:
    """计算主表与各面板的像素高度。"""
    total = max(int(total_height), 360)
    panel_flags = (
        (has_signal_panel, signal_expanded, signal_min_height, "signal"),
        (has_position_panel, position_expanded, position_min_height, "position"),
        (has_run_output, run_expanded, run_min_height, "run"),
    )

    if table_ratio is not None:
        ratio = max(0.25, min(0.75, float(table_ratio)))
        spec_by_key = {spec.key: spec for spec in _CENTER_PANEL_SPECS}
        collapsed: dict[str, int] = {}
        expanded_keys: list[str] = []
        expanded_min: dict[str, int] = {}
        for spec, (present, expanded, min_h, _key) in zip(_CENTER_PANEL_SPECS, panel_flags, strict=True):
            if not present:
                continue
            if expanded:
                expanded_keys.append(spec.key)
                expanded_min[spec.key] = max(
                    min_h,
                    panel_slot_height(True, True, spec.default_height, spec.collapsed_height, min_h),
                )
            else:
                collapsed[spec.key] = spec.collapsed_height

        table_h = max(int(total * ratio), TABLE_MIN_HEIGHT)
        fixed = sum(collapsed.values())
        remaining = total - table_h - fixed
        for key in expanded_keys:
            need = expanded_min.get(key, spec_by_key[key].default_height)
            if remaining < need:
                table_h = max(TABLE_MIN_HEIGHT, table_h - (need - remaining))
                remaining = total - table_h - fixed

        slots: dict[str, int] = dict(collapsed)
        slots["table"] = table_h
        if len(expanded_keys) == 1:
            key = expanded_keys[0]
            slots[key] = max(remaining, expanded_min.get(key, 0))
        elif expanded_keys:
            share = max(remaining // len(expanded_keys), 0)
            for key in expanded_keys:
                slots[key] = max(share, expanded_min.get(key, 0))
            overflow = sum(slots.values()) + slots["table"] - total
            if overflow > 0:
                slots["table"] = max(TABLE_MIN_HEIGHT, slots["table"] - overflow)
        return slots

    layout_slots: dict[str, int] = {}
    for spec, (present, expanded, min_h, _key) in zip(_CENTER_PANEL_SPECS, panel_flags, strict=True):
        layout_slots[spec.key] = panel_slot_height(
            present,
            expanded,
            spec.default_height,
            spec.collapsed_height,
            min_h,
        )
    table_h = max(total - sum(layout_slots.values()), TABLE_MIN_HEIGHT)
    return {"table": table_h, **layout_slots}


def _splitter_table_ratio_for_page(page: WatchlistHost) -> float | None:
    if page.page_name != "自选":
        return None
    override = getattr(page, "_watchlist_table_ratio_override", None)
    if override is not None:
        return float(override)
    from vnpy_ashare.ui.quotes.features.watchlist.prefs import load_watchlist_layout_preset
    from vnpy_ashare.ui.quotes.features.watchlist.preset_specs import PRESET_SPECS

    preset_id = load_watchlist_layout_preset()
    return PRESET_SPECS[preset_id].splitter_table_ratio


def configure_center_splitter(splitter: QtWidgets.QSplitter) -> None:
    """子面板固定高度，余量全部给主表。"""
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(6)
    for index in range(splitter.count()):
        splitter.setStretchFactor(index, 1 if index == 0 else 0)


def _normalize_saved_sizes(page: WatchlistHost, splitter: QtWidgets.QSplitter, saved: list[int]) -> list[int]:
    """按各面板展开状态校正保存高度，避免展开态却只有折叠像素导致内容被裁切。"""
    if len(saved) != splitter.count():
        return []

    panel_specs = _center_panel_by_widget(page)
    result = list(saved)

    for index in range(splitter.count()):
        widget = splitter.widget(index)
        if widget is None:
            continue
        spec = panel_specs.get(widget)
        if spec is None:
            continue
        panel = widget
        min_h = panel_min_splitter_height(
            panel,
            default_height=spec.default_height,
            collapsed_height=spec.collapsed_height,
        )
        if _panel_is_expanded(panel):
            result[index] = max(result[index], min_h)
        else:
            result[index] = spec.collapsed_height

    total = splitter_total_height(splitter)
    return clamp_primary_sizes(result, total=total, primary_min=TABLE_MIN_HEIGHT)


def apply_center_splitter_sizes(page: WatchlistHost, *, _retry: int = 0) -> None:
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

    widgets = _center_panel_widgets(page)
    signal_panel = widgets["signal"]
    position_panel = widgets["position"]
    run_panel = widgets["run"]

    sizes_map = compute_center_splitter_sizes(
        splitter_total_height(splitter),
        has_signal_panel=signal_panel is not None,
        signal_expanded=_panel_is_expanded(signal_panel) if signal_panel is not None else False,
        has_position_panel=position_panel is not None,
        position_expanded=_panel_is_expanded(position_panel) if position_panel is not None else False,
        has_run_output=run_panel is not None,
        run_expanded=_panel_is_expanded(run_panel) if run_panel is not None else False,
        signal_min_height=signal_panel.minimumHeight() if signal_panel is not None else 0,
        position_min_height=position_panel.minimumHeight() if position_panel is not None else 0,
        run_min_height=run_panel.minimumHeight() if run_panel is not None else 0,
        table_ratio=_splitter_table_ratio_for_page(page),
    )

    widget_keys = _center_panel_widgets(page)
    new_sizes: list[int] = []
    for index in range(splitter.count()):
        widget = splitter.widget(index)
        matched_key: str | None = None
        for key, panel_widget in widget_keys.items():
            if widget is panel_widget:
                matched_key = key
                break
        if matched_key is not None:
            new_sizes.append(sizes_map[matched_key])
        else:
            current = splitter.sizes()
            new_sizes.append(current[index] if index < len(current) else 0)

    if not new_sizes:
        return

    set_splitter_sizes_quiet(splitter, new_sizes)


def restore_center_splitter(page: WatchlistHost) -> None:

    signal_panel = page.signal_panel
    if signal_panel is not None:
        signal_panel.set_expanded(load_signal_panel_expanded(), emit=False)
        if hasattr(signal_panel, "sync_splitter_geometry"):
            signal_panel.sync_splitter_geometry()
    position_panel = page.position_panel
    if position_panel is not None:
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
    saved = load_center_splitter_sizes()
    if len(saved) == splitter.count():
        normalized = _normalize_saved_sizes(page, splitter, saved)
        if normalized and sum(normalized) >= 320:
            set_splitter_sizes_quiet(splitter, normalized)
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


def bind_center_splitter_persistence(page: WatchlistHost) -> None:
    """用户拖动分隔条时保存尺寸。"""
    splitter = center_splitter(page)
    if splitter is None:
        return
    bind_splitter_persistence(
        splitter,
        save_center_splitter_sizes,
        bound_flag="_center_splitter_bound",
        host=page,
    )
