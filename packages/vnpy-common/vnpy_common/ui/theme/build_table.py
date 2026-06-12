"""数据面板表格 QSS（只读、紧凑）。"""

from __future__ import annotations

from vnpy_common.ui.theme.tokens import ThemeTokens


def build_data_table_stylesheet(tokens: ThemeTokens) -> str:
    t = tokens
    table_selectors = (
        "QTableWidget#DataTable",
        "QTableWidget#PivotTable",
    )
    root = ",\n".join(table_selectors)
    item = ",\n".join(f"{name}::item" for name in table_selectors)
    item_selected = ",\n".join(f"{name}::item:selected" for name in table_selectors)
    item_hover = ",\n".join(f"{name}::item:hover" for name in table_selectors)
    item_alt = ",\n".join(f"{name}::item:alternate" for name in table_selectors)
    header = ",\n".join(f"{name} QHeaderView::section" for name in table_selectors)
    return f"""
{root} {{
    background-color: {t.depth_bg};
    gridline-color: {t.panel_border};
    border: none;
    font-size: 12px;
    color: {t.text_primary};
    selection-background-color: {t.table_selected};
    selection-color: {t.text_primary};
}}
{header} {{
    background-color: {t.header_bg};
    color: {t.header_text};
    padding: 5px 6px;
    border: none;
    border-right: 1px solid {t.header_border};
    border-bottom: 1px solid {t.header_border};
    font-size: 11px;
    font-weight: 600;
}}
{item} {{
    padding: 4px 6px;
    border: none;
}}
{item_selected} {{
    background-color: {t.table_selected};
    color: {t.text_primary};
}}
{item_hover} {{
    background-color: {t.table_hover};
}}
{item_alt} {{
    background-color: {t.table_alt};
}}
"""
