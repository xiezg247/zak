"""B 站 API 响应 → FeedItemDraft。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from vnpy_ashare.domain.feed.models import FeedItemDraft


def normalize_video(raw: dict[str, Any], *, author_name: str) -> FeedItemDraft | None:
    bvid = str(raw.get("bvid") or "").strip()
    if not bvid:
        return None
    title = str(raw.get("title") or "").strip()
    description = str(raw.get("description") or "").strip()
    pubdate = int(raw.get("created") or raw.get("pubdate") or 0)
    return FeedItemDraft(
        external_id=bvid,
        item_type="video",
        title=title,
        summary=description[:500],
        url=f"https://www.bilibili.com/video/{bvid}",
        author_name=author_name,
        published_at=_iso_from_unix(pubdate),
        payload={
            "cover_url": str(raw.get("pic") or raw.get("cover") or ""),
            "view_count": int(raw.get("play") or raw.get("view") or 0),
            "raw_pubdate": pubdate,
        },
    )


def normalize_dynamic(raw: dict[str, Any], *, author_name: str) -> FeedItemDraft | None:
    modules = raw.get("modules") or {}
    module_dynamic = modules.get("module_dynamic") or {}
    major = module_dynamic.get("major") or {}
    desc = module_dynamic.get("desc") or {}
    id_str = str(raw.get("id_str") or raw.get("id") or "").strip()
    if not id_str:
        return None

    title = ""
    summary = ""
    item_type = "dynamic"
    url = f"https://t.bilibili.com/{id_str}"
    cover_url = ""

    archive = major.get("archive") or {}
    if archive:
        item_type = "video"
        bvid = str(archive.get("bvid") or "").strip()
        title = str(archive.get("title") or "").strip()
        summary = str(archive.get("desc") or "").strip()
        if bvid:
            url = f"https://www.bilibili.com/video/{bvid}"
        cover_url = str(archive.get("cover") or "")
    else:
        opus = major.get("opus") or {}
        if opus:
            title = str(opus.get("title") or "").strip()
            summary = _join_rich_text(opus.get("summary") or desc.get("text") or "")
            cover_url = _first_image(opus)
        else:
            summary = str(desc.get("text") or "").strip()
            draw = major.get("draw") or {}
            items = draw.get("items") or []
            if items and isinstance(items[0], dict):
                cover_url = str(items[0].get("src") or "")

    if not title:
        title = summary[:80] or "新动态"

    pub_ts = int((raw.get("modules") or {}).get("module_author", {}).get("pub_ts") or 0)
    if pub_ts <= 0:
        pub_ts = int(raw.get("pub_ts") or 0)

    return FeedItemDraft(
        external_id=id_str,
        item_type=item_type,
        title=title,
        summary=summary[:500],
        url=url,
        author_name=author_name,
        published_at=_iso_from_unix(pub_ts),
        payload={
            "cover_url": cover_url,
            "dynamic_type": str(raw.get("type") or ""),
            "raw_pubdate": pub_ts,
        },
    )


def _join_rich_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("text") or "").strip()
    if isinstance(value, list):
        parts = [_join_rich_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    return ""


def _first_image(opus: dict[str, Any]) -> str:
    pics = opus.get("pics") or []
    if pics and isinstance(pics[0], dict):
        return str(pics[0].get("url") or pics[0].get("src") or "")
    return ""


def _iso_from_unix(ts: int) -> str:
    if ts <= 0:
        return datetime.now().isoformat(timespec="seconds")
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
