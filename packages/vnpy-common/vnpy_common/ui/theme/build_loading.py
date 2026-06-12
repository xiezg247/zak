"""内容区加载遮罩 QSS。"""

from __future__ import annotations

from vnpy_common.ui.theme.tokens import ThemeTokens


def build_content_loading_stylesheet(tokens: ThemeTokens) -> str:
    t = tokens
    return f"""
QWidget#ContentLoadingOverlay {{
    background-color: rgba(12, 12, 16, 0.78);
}}
QWidget#ContentLoadingPanel {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 10px;
}}
QLabel#ContentLoadingTitle {{
    color: {t.text_primary};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#ContentLoadingHint {{
    color: {t.text_muted};
    font-size: 12px;
}}
QProgressBar#ContentLoadingBar {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
}}
QProgressBar#ContentLoadingBar::chunk {{
    background-color: {t.accent};
    border-radius: 3px;
}}
"""
