"""B 站用户搜索与资料。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.bilibili.client import BilibiliApiError, BilibiliClient


def search_users(client: BilibiliClient, keyword: str, *, limit: int = 5) -> list[dict[str, Any]]:
    keyword = keyword.strip()
    if not keyword:
        return []
    data = client._get_json(
        "/x/web-interface/search/type",
        params={
            "search_type": "bili_user",
            "keyword": keyword,
            "page": 1,
        },
        signed=False,
    )
    result = data.get("result") or []
    users: list[dict[str, Any]] = []
    for group in result:
        if not isinstance(group, dict):
            continue
        if str(group.get("result_type", "")) != "bili_user":
            continue
        for item in group.get("data") or []:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("mid") or "")
            if not mid:
                continue
            users.append(
                {
                    "mid": mid,
                    "name": str(item.get("uname") or item.get("title") or ""),
                    "avatar": str(item.get("upic") or item.get("face") or ""),
                    "sign": str(item.get("usign") or ""),
                }
            )
            if len(users) >= limit:
                return users
    return users


def get_user_profile(client: BilibiliClient, mid: str) -> dict[str, str]:
    mid = str(mid).strip()
    if not mid:
        raise BilibiliApiError("mid 不能为空")
    data = client._get_json("/x/space/acc/info", params={"mid": mid}, signed=False)
    return {
        "mid": mid,
        "name": str(data.get("name") or ""),
        "avatar": str(data.get("face") or ""),
        "sign": str(data.get("sign") or ""),
    }
