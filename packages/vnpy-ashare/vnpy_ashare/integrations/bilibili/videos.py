"""B 站投稿视频列表。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.bilibili.client import BilibiliApiError, BilibiliClient


def list_recent_videos(client: BilibiliClient, mid: str, *, count: int = 10) -> list[dict[str, Any]]:
    mid = str(mid).strip()
    if not mid:
        raise BilibiliApiError("mid 不能为空")
    count = max(1, min(int(count), 30))
    data = client._get_json(
        "/x/space/arc/search",
        params={
            "mid": mid,
            "ps": count,
            "pn": 1,
            "order": "pubdate",
        },
        signed=False,
    )
    videos: list[dict[str, Any]] = []
    for item in data.get("list", {}).get("vlist", []) or []:
        if not isinstance(item, dict):
            continue
        videos.append(item)
    return videos
