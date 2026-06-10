"""RichText / 内联 HTML 用色（由 ThemeTokens 推导）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_common.ui.theme.tokens import ThemeTokens


@dataclass(frozen=True)
class HtmlPalette:
    label: str
    hint: str
    body: str
    section: str
    error: str
    warning: str
    muted: str


def html_palette(t: ThemeTokens) -> HtmlPalette:
    return HtmlPalette(
        label=t.text_secondary,
        hint=t.text_muted,
        body=t.text_primary,
        section=t.accent,
        error=t.semantic_error,
        warning=t.semantic_warning,
        muted=t.text_muted,
    )
