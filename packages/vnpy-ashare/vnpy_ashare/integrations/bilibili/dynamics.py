"""B 站空间动态。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.bilibili.client import BilibiliApiError, BilibiliClient


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
