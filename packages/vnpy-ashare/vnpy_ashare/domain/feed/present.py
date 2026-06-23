"""信息流展示辅助。"""

from __future__ import annotations

from vnpy_ashare.domain.feed.models import FeedItem


def feed_item_detail_text(item: FeedItem) -> str:
    """条目详情正文：优先 summary，视频无简介时展示播放量等元数据。"""
    summary = (item.summary or "").strip()
    if summary and summary != (item.title or "").strip():
        return summary
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
