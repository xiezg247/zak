"""RichText 状态 / 段落格式化（基于 html_palette）。"""

from __future__ import annotations

from vnpy_common.ui.theme.html_palette import html_palette
from vnpy_common.ui.theme.tokens import ThemeTokens


def format_status_html(
    message: str,
    *,
    hint: str = "",
    tone: str = "loading",
    tokens: ThemeTokens | None = None,
) -> str:
    """tone: loading | info | error | warning"""
    from vnpy_common.ui.theme import theme_manager

    colors = html_palette(tokens or theme_manager().tokens())
    color_map = {
        "loading": colors.section,
        "info": colors.body,
        "error": colors.error,
        "warning": colors.warning,
    }
    color = color_map.get(tone, colors.body)
    prefix = '<span style="font-size:15px;opacity:0.85;">◌</span> ' if tone == "loading" else ""
    hint_html = f'<p style="margin:8px 0 0;color:{colors.muted};font-size:12px;">{hint}</p>' if hint else ""
    return f'<p style="margin:0;color:{color};font-size:13px;">{prefix}{message}</p>{hint_html}'


def format_loading_html(
    message: str,
    *,
    hint: str = "",
    tokens: ThemeTokens | None = None,
) -> str:
    return format_status_html(message, hint=hint, tone="loading", tokens=tokens)
