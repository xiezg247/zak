"""AI 助手消息中的可点击标的链接（Markdown → zak://symbol/…）。"""

from __future__ import annotations

import re
from typing import cast
from urllib.parse import quote, unquote

_SYMBOL_SCHEME = "zak://symbol/"

_VT_SYMBOL_RE = re.compile(
    r"(?<![\d./])"
    r"(\d{6}\.(?:SSE|SZSE|BSE|SH|SZ|BJ))"
    r"(?![.\d])",
    re.IGNORECASE,
)
_BARE_CODE_RE = re.compile(
    r"(?<![\d/])"
    r"(\d{6})"
    r"(?![.\d])",
)
_FENCE_RE = re.compile(r"(```[\s\S]*?```)", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")


def symbol_href(vt_symbol: str) -> str:
    return f"{_SYMBOL_SCHEME}{quote(vt_symbol, safe='.')}"


def parse_symbol_href(url: str) -> str | None:
    text = str(url or "").strip()
    if not text.startswith(_SYMBOL_SCHEME):
        return None
    raw = unquote(text[len(_SYMBOL_SCHEME) :].split("?", 1)[0].strip())
    return normalize_vt_symbol(raw)


def normalize_vt_symbol(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        from vnpy_ashare.ai.context.symbol import parse_stock_symbol

        item = parse_stock_symbol(text)
        if item is not None:
            return cast(str, item.vt_symbol)
    except ImportError:
        pass
    return _normalize_vt_symbol_fallback(text)


def linkify_markdown(text: str) -> str:
    """将 Markdown 正文中的 vt_symbol / 6 位代码转为可点击链接。"""
    if not text.strip():
        return text
    parts: list[str] = []
    pos = 0
    for match in _FENCE_RE.finditer(text):
        if match.start() > pos:
            parts.append(_linkify_segment(text[pos : match.start()]))
        parts.append(match.group(0))
        pos = match.end()
    parts.append(_linkify_segment(text[pos:]))
    return "".join(parts)


def _linkify_segment(text: str) -> str:
    parts: list[str] = []
    pos = 0
    for match in _MD_LINK_RE.finditer(text):
        if match.start() > pos:
            parts.append(_linkify_plain(text[pos : match.start()]))
        parts.append(match.group(0))
        pos = match.end()
    parts.append(_linkify_plain(text[pos:]))
    return "".join(parts)


def _linkify_plain(text: str) -> str:
    parts: list[str] = []
    pos = 0
    for match in _INLINE_CODE_RE.finditer(text):
        if match.start() > pos:
            parts.append(_linkify_codes(text[pos : match.start()]))
        parts.append(match.group(0))
        pos = match.end()
    parts.append(_linkify_codes(text[pos:]))
    return "".join(parts)


def _linkify_codes(text: str) -> str:
    text = _VT_SYMBOL_RE.sub(_replace_vt_symbol, text)
    return _BARE_CODE_RE.sub(_replace_bare_code, text)


def _replace_vt_symbol(match: re.Match[str]) -> str:
    raw = match.group(1)
    vt = normalize_vt_symbol(raw)
    if vt is None:
        return raw
    return f"[{raw}]({symbol_href(vt)})"


def _replace_bare_code(match: re.Match[str]) -> str:
    raw = match.group(1)
    vt = normalize_vt_symbol(raw)
    if vt is None:
        return raw
    return f"[{raw}]({symbol_href(vt)})"


def _normalize_vt_symbol_fallback(text: str) -> str | None:
    upper = text.upper()
    if "." not in upper:
        return None
    code, suffix = upper.rsplit(".", 1)
    if len(code) != 6 or not code.isdigit():
        return None
    exchange_map = {
        "SSE": "SSE",
        "SH": "SSE",
        "SZSE": "SZSE",
        "SZ": "SZSE",
        "BSE": "BSE",
        "BJ": "BSE",
    }
    exchange = exchange_map.get(suffix)
    if exchange is None:
        return None
    return f"{code}.{exchange}"
