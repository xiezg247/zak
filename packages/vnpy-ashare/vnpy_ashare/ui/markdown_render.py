"""Markdown 预览（优先复用 vnpy-llm 渲染器）。"""

from __future__ import annotations

import html
import re


def render_markdown_html(text: str) -> str:
    try:
        from vnpy_llm.ui.panel.md_renderer import render_markdown

        return render_markdown(text)
    except ImportError:
        return _fallback_html(text)


def _fallback_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    paragraphs = escaped.replace("\r\n", "\n").split("\n\n")
    body = "</p><p>".join(p.replace("\n", "<br>") for p in paragraphs if p.strip())
    return f"<html><head><meta charset='utf-8'></head><body style='font-family:sans-serif;line-height:1.5'><p>{body}</p></body></html>"
