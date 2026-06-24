"""B 站用户搜索与资料。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.bilibili.client import BilibiliApiError, BilibiliClient

_SEARCH_USER_PATH = "/x/web-interface/wbi/search/type"


def search_users(client: BilibiliClient, keyword: str, *, limit: int = 5) -> list[dict[str, Any]]:
    keyword = keyword.strip()
    if not keyword:
        return []
    data = client._get_json(
        _SEARCH_USER_PATH,
        params={
            "search_type": "bili_user",
            "keyword": keyword,
            "page": 1,
        },
        signed=True,
    )
    users: list[dict[str, Any]] = []
    for item in _iter_search_user_items(data.get("result")):
        user = _normalize_search_user(item)
        if user is None:
            continue
        users.append(user)
        if len(users) >= limit:
            break
    return users


def _iter_search_user_items(result: Any):
    if not isinstance(result, list):
        return
    for item in result:
        if not isinstance(item, dict):
            continue
        if str(item.get("result_type") or "") == "bili_user":
            for row in item.get("data") or []:
                if isinstance(row, dict):
                    yield row
            continue
        if str(item.get("type") or "") == "bili_user":
            yield item


def _normalize_search_user(item: dict[str, Any]) -> dict[str, str] | None:
    mid = str(item.get("mid") or "")
    if not mid:
        return None
    avatar = str(item.get("upic") or item.get("face") or "")
    if avatar.startswith("//"):
        avatar = f"https:{avatar}"
    return {
        "mid": mid,
        "name": str(item.get("uname") or item.get("title") or ""),
        "avatar": avatar,
        "sign": str(item.get("usign") or item.get("sign") or ""),
    }


def get_user_profile(client: BilibiliClient, mid: str) -> dict[str, str]:
    mid = str(mid).strip()
    if not mid:
        raise BilibiliApiError("mid 不能为空")
    data = client._get_json("/x/space/acc/info", params={"mid": mid}, signed=False)
    avatar = str(data.get("face") or "")
    if avatar.startswith("//"):
        avatar = f"https:{avatar}"
    return {
        "mid": mid,
        "name": str(data.get("name") or ""),
        "avatar": avatar,
        "sign": str(data.get("sign") or ""),
    }
