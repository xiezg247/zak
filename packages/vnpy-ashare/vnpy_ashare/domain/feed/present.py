"""信息流展示辅助。"""

from __future__ import annotations

import re

from vnpy_ashare.domain.feed.models import FeedItem

_GENERIC_TITLES = frozenset({"新动态", "（无标题）"})
_IMAGE_DYNAMIC_RE = re.compile(r"^图片动态[（(](\d+)\s*张[）)]$")


def feed_item_title_text(item: FeedItem) -> str:
    """列表标题行：优先真实标题，纯文字动态取首行。"""
    title = (item.title or "").strip()
    summary = (item.summary or "").strip()
    image_match = _IMAGE_DYNAMIC_RE.match(title)
    if image_match and (not summary or summary == title):
        return "图片动态"
    if title and title not in _GENERIC_TITLES:
        return title
    if summary:
        return _first_line(summary)
    if item.item_type == "dynamic" and item.payload.get("dynamic_type") == "DYNAMIC_TYPE_DRAW":
        return "图片动态"
    return title or "（无标题）"


def feed_item_detail_text(item: FeedItem) -> str:
    """列表详情行：正文摘要；与标题重复时不展示。"""
    summary = (item.summary or "").strip()
    title = feed_item_title_text(item)
    raw_title = (item.title or "").strip()

    image_match = _IMAGE_DYNAMIC_RE.match(raw_title) or _IMAGE_DYNAMIC_RE.match(summary)
    if image_match and (not summary or summary == raw_title or _IMAGE_DYNAMIC_RE.match(summary)):
        count = image_match.group(1)
        cover = (item.payload.get("cover_url") or "").strip()
        hint = f"共 {count} 张图片"
        if cover:
            hint += "，双击在浏览器查看"
        return hint

    if summary:
        if summary == title:
            return ""
        if summary.startswith(title):
            rest = summary[len(title) :].lstrip("\n ").strip()
            if rest:
                return rest
        else:
            return summary

    if item.item_type == "dynamic":
        dtype = str(item.payload.get("dynamic_type") or "")
        cover = (item.payload.get("cover_url") or "").strip()
        if dtype == "DYNAMIC_TYPE_DRAW":
            if cover:
                return "含图片，双击在浏览器查看"
            return "无文字说明，双击在浏览器查看"

    view_count = int(item.payload.get("view_count") or 0)
    if item.item_type == "video" and view_count > 0:
        return f"播放 {view_count:,}"
    return ""


def feed_item_meta_text(item: FeedItem) -> str:
    type_label = {"video": "视频", "dynamic": "动态", "article": "专栏"}.get(item.item_type, item.item_type)
    parts = [type_label, item.author_name]
    view_count = int(item.payload.get("view_count") or 0)
    if item.item_type == "video" and view_count > 0:
        parts.append(f"播放 {view_count:,}")
    return " · ".join(part for part in parts if part)


def _first_line(text: str, max_len: int = 80) -> str:
    line = text.strip().split("\n", 1)[0].strip()
    if len(line) <= max_len:
        return line
    return f"{line[: max_len - 1]}…"
