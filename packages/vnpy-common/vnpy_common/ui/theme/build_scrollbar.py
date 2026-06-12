"""高对比度滚动条 QSS（ThemeTokens 驱动，供终端 / 表格 / 弹窗复用）。"""

from __future__ import annotations

from vnpy_common.ui.theme.tokens import ThemeTokens


def _selector_group(*selectors: str) -> str:
    return ",\n".join(selectors)


def build_prominent_scrollbar_stylesheet(
    tokens: ThemeTokens,
    *,
    area_names: tuple[str, ...] = (),
    bar_vertical_names: tuple[str, ...] = (),
    bar_horizontal_names: tuple[str, ...] = (),
    width: int = 12,
    height: int = 12,
    min_handle_vertical: int = 48,
    min_handle_horizontal: int = 48,
) -> str:
    """生成高对比度滚动条 QSS。

    - ``area_names``：QScrollArea 的 objectName，作用于其子 QScrollBar
    - ``bar_*_names``：QScrollBar 自身的 objectName（表格 / PlainTextEdit 等）
    """
    t = tokens
    track = t.panel_border
    handle = t.combo_hover_border
    handle_hover = t.accent
    handle_pressed = t.accent_hover
    handle_border = t.panel_border
    page_bg = "transparent"

    vertical_selectors: list[str] = []
    for name in area_names:
        vertical_selectors.append(f"QScrollArea#{name} QScrollBar:vertical")
    for name in bar_vertical_names:
        vertical_selectors.append(f"QScrollBar#{name}:vertical")
    if not vertical_selectors:
        return ""

    vertical_root = _selector_group(*vertical_selectors)
    vertical_handle = _selector_group(
        *[f"QScrollArea#{name} QScrollBar::handle:vertical" for name in area_names],
        *[f"QScrollBar#{name}::handle:vertical" for name in bar_vertical_names],
    )
    vertical_handle_hover = _selector_group(
        *[f"QScrollArea#{name} QScrollBar::handle:vertical:hover" for name in area_names],
        *[f"QScrollBar#{name}::handle:vertical:hover" for name in bar_vertical_names],
    )
    vertical_handle_pressed = _selector_group(
        *[f"QScrollArea#{name} QScrollBar::handle:vertical:pressed" for name in area_names],
        *[f"QScrollBar#{name}::handle:vertical:pressed" for name in bar_vertical_names],
    )
    vertical_lines = _selector_group(
        *[f"QScrollArea#{name} QScrollBar::add-line:vertical" for name in area_names],
        *[f"QScrollArea#{name} QScrollBar::sub-line:vertical" for name in area_names],
        *[f"QScrollBar#{name}::add-line:vertical" for name in bar_vertical_names],
        *[f"QScrollBar#{name}::sub-line:vertical" for name in bar_vertical_names],
    )
    vertical_pages = _selector_group(
        *[f"QScrollArea#{name} QScrollBar::add-page:vertical" for name in area_names],
        *[f"QScrollArea#{name} QScrollBar::sub-page:vertical" for name in area_names],
        *[f"QScrollBar#{name}::add-page:vertical" for name in bar_vertical_names],
        *[f"QScrollBar#{name}::sub-page:vertical" for name in bar_vertical_names],
    )

    blocks = [
        f"""
{vertical_root} {{
    background-color: {track};
    width: {width}px;
    margin: 2px 1px 2px 0;
    border: none;
    border-radius: {max(width // 2, 4)}px;
}}
{vertical_handle} {{
    background-color: {handle};
    min-height: {min_handle_vertical}px;
    border-radius: {max(width // 2 - 1, 3)}px;
    margin: 2px;
    border: 1px solid {handle_border};
}}
{vertical_handle_hover} {{
    background-color: {handle_hover};
    border-color: {handle_hover};
}}
{vertical_handle_pressed} {{
    background-color: {handle_pressed};
    border-color: {handle_pressed};
}}
{vertical_lines} {{
    height: 0;
    background: none;
}}
{vertical_pages} {{
    background: {page_bg};
}}
"""
    ]

    horizontal_selectors: list[str] = []
    for name in area_names:
        horizontal_selectors.append(f"QScrollArea#{name} QScrollBar:horizontal")
    for name in bar_horizontal_names:
        horizontal_selectors.append(f"QScrollBar#{name}:horizontal")
    if horizontal_selectors:
        horizontal_root = _selector_group(*horizontal_selectors)
        horizontal_handle = _selector_group(
            *[f"QScrollArea#{name} QScrollBar::handle:horizontal" for name in area_names],
            *[f"QScrollBar#{name}::handle:horizontal" for name in bar_horizontal_names],
        )
        horizontal_handle_hover = _selector_group(
            *[f"QScrollArea#{name} QScrollBar::handle:horizontal:hover" for name in area_names],
            *[f"QScrollBar#{name}::handle:horizontal:hover" for name in bar_horizontal_names],
        )
        horizontal_handle_pressed = _selector_group(
            *[f"QScrollArea#{name} QScrollBar::handle:horizontal:pressed" for name in area_names],
            *[f"QScrollBar#{name}::handle:horizontal:pressed" for name in bar_horizontal_names],
        )
        horizontal_lines = _selector_group(
            *[f"QScrollArea#{name} QScrollBar::add-line:horizontal" for name in area_names],
            *[f"QScrollArea#{name} QScrollBar::sub-line:horizontal" for name in area_names],
            *[f"QScrollBar#{name}::add-line:horizontal" for name in bar_horizontal_names],
            *[f"QScrollBar#{name}::sub-line:horizontal" for name in bar_horizontal_names],
        )
        horizontal_pages = _selector_group(
            *[f"QScrollArea#{name} QScrollBar::add-page:horizontal" for name in area_names],
            *[f"QScrollArea#{name} QScrollBar::sub-page:horizontal" for name in area_names],
            *[f"QScrollBar#{name}::add-page:horizontal" for name in bar_horizontal_names],
            *[f"QScrollBar#{name}::sub-page:horizontal" for name in bar_horizontal_names],
        )
        blocks.append(
            f"""
{horizontal_root} {{
    background-color: {track};
    height: {height}px;
    margin: 0 2px 1px 2px;
    border: none;
    border-radius: {max(height // 2, 4)}px;
}}
{horizontal_handle} {{
    background-color: {handle};
    min-width: {min_handle_horizontal}px;
    border-radius: {max(height // 2 - 1, 3)}px;
    margin: 2px;
    border: 1px solid {handle_border};
}}
{horizontal_handle_hover} {{
    background-color: {handle_hover};
    border-color: {handle_hover};
}}
{horizontal_handle_pressed} {{
    background-color: {handle_pressed};
    border-color: {handle_pressed};
}}
{horizontal_lines} {{
    width: 0;
    background: none;
}}
{horizontal_pages} {{
    background: {page_bg};
}}
"""
        )

    return "".join(blocks)


def build_terminal_scrollbar_stylesheet(tokens: ThemeTokens) -> str:
    """终端通用高对比度滚动条（弹窗、表格、滚动区）。"""
    return build_prominent_scrollbar_stylesheet(
        tokens,
        area_names=("TerminalScrollArea", "AiMessageScroll"),
        bar_vertical_names=(
            "TerminalScrollBarVertical",
            "AiMessageScrollBar",
        ),
        bar_horizontal_names=("TerminalScrollBarHorizontal",),
    )


def build_market_table_scrollbar_stylesheet(tokens: ThemeTokens) -> str:
    """行情表格专用加宽滚动条（保留 MarketTableScroll 命名）。"""
    t = tokens
    return build_prominent_scrollbar_stylesheet(
        t,
        bar_vertical_names=("MarketTableScroll",),
        width=18,
        min_handle_vertical=52,
    ) + f"""
QScrollBar#MarketTableScroll:vertical:disabled {{
    background-color: {t.combo_popup_border};
}}
QScrollBar#MarketTableScroll::handle:vertical:disabled {{
    background-color: {t.combo_border};
    border-color: {t.header_border};
}}
QScrollBar#MarketTableScroll::add-page:vertical,
QScrollBar#MarketTableScroll::sub-page:vertical {{
    background: {t.panel_border};
}}
"""
