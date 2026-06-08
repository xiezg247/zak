"""Markdown → HTML 渲染工具，供 QTextBrowser 使用。"""

from __future__ import annotations

import markdown as _md_lib
from markdown.extensions import codehilite, fenced_code, tables


def render_markdown(text: str) -> str:
    """将 Markdown 文本转换为 HTML，附带内置暗色 CSS。"""
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
    return _HTML_TEMPLATE_HEAD + body + _HTML_TEMPLATE_TAIL


_HTML_TEMPLATE_HEAD = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {
    font-family: -apple-system, "Segoe UI", "Noto Sans SC", sans-serif;
    font-size: 13px;
    line-height: 1.65;
    color: #e0e0e0;
    background-color: transparent;
    margin: 0;
    padding: 0;
}
p { margin: 0 0 0.6em 0; }
p:last-child { margin-bottom: 0; }
h1, h2, h3, h4, h5, h6 {
    color: #c8d0e0;
    margin: 0.8em 0 0.4em 0;
    font-weight: 600;
    line-height: 1.3;
}
h1 { font-size: 1.35em; }
h2 { font-size: 1.2em; }
h3 { font-size: 1.1em; }
pre {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 12px;
    overflow-x: auto;
    margin: 0.5em 0;
    font-size: 12px;
    line-height: 1.5;
}
code {
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
    background-color: #1a1a24;
    padding: 1px 4px;
    border-radius: 3px;
    color: #e0a060;
}
pre code {
    background-color: transparent;
    padding: 0;
    border-radius: 0;
    color: #e0e0e0;
}
blockquote {
    border-left: 3px solid #4a9eff;
    padding: 4px 0 4px 12px;
    margin: 0.5em 0;
    color: #a0b0c0;
    background-color: #1a1a26;
    border-radius: 0 4px 4px 0;
}
ul, ol {
    margin: 0.3em 0;
    padding-left: 1.5em;
}
li {
    margin: 0.15em 0;
}
table {
    border-collapse: collapse;
    margin: 0.5em 0;
    font-size: 12px;
    width: 100%;
}
th, td {
    border: 1px solid #2a2a36;
    padding: 4px 8px;
    text-align: left;
}
th {
    background-color: #1e1e2a;
    color: #a0b0c0;
    font-weight: 600;
}
td {
    background-color: #18181f;
}
a {
    color: #4a9eff;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
strong {
    color: #e8e8f0;
    font-weight: 600;
}
hr {
    border: none;
    border-top: 1px solid #2a2a36;
    margin: 0.8em 0;
}
.highlight { background-color: #0d1117; }
.highlight .hll { background-color: #272822; }
.highlight .c { color: #6a737d; }
.highlight .k { color: #ff7b72; }
.highlight .s { color: #a5d6ff; }
.highlight .n { color: #c9d1d9; }
.highlight .o { color: #ff7b72; }
.highlight .p { color: #c9d1d9; }
</style>
</head>
<body>
"""

_HTML_TEMPLATE_TAIL = """
</body>
</html>"""
