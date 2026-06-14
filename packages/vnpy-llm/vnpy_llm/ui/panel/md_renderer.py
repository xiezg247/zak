"""Markdown → HTML 渲染工具，供 QTextBrowser 使用。"""

from __future__ import annotations

import markdown as _md_lib
from markdown.extensions import codehilite, fenced_code, tables

from vnpy_common.ui.theme.tokens import ThemeTokens


def render_markdown(text: str, *, tokens: ThemeTokens | None = None) -> str:
    """将 Markdown 文本转换为 HTML，CSS 随当前主题 tokens 生成。"""
    if tokens is None:
        from vnpy_common.ui.theme import theme_manager

        tokens = theme_manager().tokens()
    md = _md_lib.Markdown(
        extensions=[
            fenced_code.FencedCodeExtension(),
            codehilite.CodeHiliteExtension(guess_lang=True, css_class="highlight"),
            tables.TableExtension(),
            "nl2br",
            "sane_lists",
        ]
    )
    body = md.convert(text)
    css = _build_markdown_css(tokens)
    return _HTML_TEMPLATE_HEAD.format(css=css) + body + _HTML_TEMPLATE_TAIL


def _build_markdown_css(t: ThemeTokens) -> str:
    if t.id == "light":
        code_inline_color = "#b45309"
        pre_code_color = t.text_primary
        highlight = _LIGHT_HIGHLIGHT_CSS.format(
            bg=t.depth_bg,
            hll="#eef2ff",
            comment="#6a737d",
            keyword="#d73a49",
            string="#032f62",
            name=t.text_primary,
            operator="#d73a49",
            punct=t.text_primary,
        )
    else:
        code_inline_color = "#e0a060"
        pre_code_color = t.text_primary
        highlight = _DARK_HIGHLIGHT_CSS.format(
            bg="#0d1117",
            hll="#272822",
            comment="#6a737d",
            keyword="#ff7b72",
            string="#a5d6ff",
            name="#c9d1d9",
            operator="#ff7b72",
            punct="#c9d1d9",
        )

    return f"""
body {{
    font-family: -apple-system, "Segoe UI", "Noto Sans SC", sans-serif;
    font-size: 13px;
    line-height: 1.65;
    color: {t.text_primary};
    background-color: transparent;
    margin: 0;
    padding: 0;
}}
p {{ margin: 0 0 0.6em 0; }}
p:last-child {{ margin-bottom: 0; }}
h1, h2, h3, h4, h5, h6 {{
    color: {t.text_section};
    margin: 0.8em 0 0.4em 0;
    font-weight: 600;
    line-height: 1.3;
}}
h1 {{ font-size: 1.35em; }}
h2 {{ font-size: 1.2em; }}
h3 {{ font-size: 1.1em; }}
pre {{
    background-color: {t.depth_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    padding: 10px 12px;
    overflow-x: auto;
    margin: 0.5em 0;
    font-size: 12px;
    line-height: 1.5;
}}
code {{
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
    background-color: {t.table_alt};
    padding: 1px 4px;
    border-radius: 3px;
    color: {code_inline_color};
}}
pre code {{
    background-color: transparent;
    padding: 0;
    border-radius: 0;
    color: {pre_code_color};
}}
blockquote {{
    border-left: 3px solid {t.accent};
    padding: 4px 0 4px 12px;
    margin: 0.5em 0;
    color: {t.text_secondary};
    background-color: {t.panel_bg};
    border-radius: 0 4px 4px 0;
}}
ul, ol {{
    margin: 0.3em 0;
    padding-left: 1.5em;
}}
li {{
    margin: 0.15em 0;
}}
table {{
    border-collapse: collapse;
    margin: 0.5em 0;
    font-size: 12px;
    width: 100%;
}}
th, td {{
    border: 1px solid {t.table_grid};
    padding: 4px 8px;
    text-align: left;
}}
th {{
    background-color: {t.header_bg};
    color: {t.header_text};
    font-weight: 600;
}}
td {{
    background-color: {t.table_bg};
    color: {t.text_primary};
}}
a {{
    color: {t.accent};
    text-decoration: none;
}}
a:hover {{
    text-decoration: underline;
}}
a[href^="zak://symbol/"] {{
    font-weight: 500;
}}
strong {{
    color: {t.text_primary};
    font-weight: 600;
}}
hr {{
    border: none;
    border-top: 1px solid {t.table_grid};
    margin: 0.8em 0;
}}
{highlight}
"""


_DARK_HIGHLIGHT_CSS = """
.highlight {{ background-color: {bg}; }}
.highlight .hll {{ background-color: {hll}; }}
.highlight .c {{ color: {comment}; }}
.highlight .k {{ color: {keyword}; }}
.highlight .s {{ color: {string}; }}
.highlight .n {{ color: {name}; }}
.highlight .o {{ color: {operator}; }}
.highlight .p {{ color: {punct}; }}
"""

_LIGHT_HIGHLIGHT_CSS = _DARK_HIGHLIGHT_CSS


_HTML_TEMPLATE_HEAD = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{css}
</style>
</head>
<body>
"""

_HTML_TEMPLATE_TAIL = """
</body>
</html>"""
