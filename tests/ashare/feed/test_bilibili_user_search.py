"""B 站用户搜索单测。"""

from __future__ import annotations

from vnpy_ashare.integrations.bilibili.user import _iter_search_user_items, _normalize_search_user


def test_iter_search_user_items_flat_wbi_result() -> None:
    rows = list(
        _iter_search_user_items(
            [
                {"type": "bili_user", "mid": 1, "uname": "A"},
                {"type": "video", "bvid": "BV1"},
            ]
        )
    )
    assert len(rows) == 1
    assert rows[0]["mid"] == 1


def test_iter_search_user_items_legacy_grouped_result() -> None:
    rows = list(
        _iter_search_user_items(
            [
                {
                    "result_type": "bili_user",
                    "data": [{"mid": 2, "uname": "B"}],
                }
            ]
        )
    )
    assert len(rows) == 1
    assert rows[0]["uname"] == "B"


def test_normalize_search_user_prefixes_avatar() -> None:
    user = _normalize_search_user({"mid": 3, "uname": "C", "upic": "//example.com/a.jpg"})
    assert user is not None
    assert user["avatar"] == "https://example.com/a.jpg"
    assert user["name"] == "C"
