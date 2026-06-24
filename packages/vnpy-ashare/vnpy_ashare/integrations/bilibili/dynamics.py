"""B 站空间动态。"""

from __future__ import annotations

import time
from typing import Any

from vnpy_ashare.integrations.bilibili.client import BilibiliApiError, BilibiliClient

_SPACE_FEATURES = (
    "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,forwardListHidden,decorationCard,commentsNewVersion,onlyfansAssetsV2,ugcDelete,onlyfansQaCard"
)
_DETAIL_FEATURES = "itemOpusStyle,opusBigCover,onlyfansVote,endFooterHidden,decorationCard,onlyfansAssetsV2,ugcDelete,onlyfansQaCard,commentsNewVersion"
_DETAIL_FETCH_SLEEP_SEC = 0.35


def list_recent_dynamics(client: BilibiliClient, mid: str, *, count: int = 10) -> list[dict[str, Any]]:
    mid = str(mid).strip()
    if not mid:
        raise BilibiliApiError("mid 不能为空")
    count = max(1, min(int(count), 20))
    data = client._get_json(
        "/x/polymer/web-dynamic/v1/feed/space",
        params={
            "host_mid": mid,
            "offset": "",
            "platform": "web",
            "features": _SPACE_FEATURES,
        },
        signed=True,
    )
    items: list[dict[str, Any]] = []
    for item in data.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        items.append(item)
        if len(items) >= count:
            break
    return items


def dynamic_pub_ts(raw: dict[str, Any]) -> int:
    modules = raw.get("modules") or {}
    author = modules.get("module_author") or {}
    return int(author.get("pub_ts") or raw.get("pub_ts") or 0)


def get_dynamic_detail(client: BilibiliClient, dynamic_id: str) -> dict[str, Any] | None:
    dynamic_id = str(dynamic_id).strip()
    if not dynamic_id:
        return None
    data = client._get_json(
        "/x/polymer/web-dynamic/v1/detail",
        params={
            "id": dynamic_id,
            "platform": "web",
            "features": _DETAIL_FEATURES,
        },
        signed=True,
    )
    item = data.get("item")
    return item if isinstance(item, dict) else None


def sleep_before_detail_fetch() -> None:
    time.sleep(_DETAIL_FETCH_SLEEP_SEC)
