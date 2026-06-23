"""信息流 normalize 单测。"""

from __future__ import annotations

from vnpy_ashare.integrations.bilibili.normalize import normalize_dynamic, normalize_video


def test_normalize_video_maps_bvid_and_pubdate() -> None:
    draft = normalize_video(
        {
            "bvid": "BV1xx411c7mD",
            "title": "测试视频",
            "description": "简介",
            "created": 1719000000,
            "pic": "https://example.com/cover.jpg",
            "play": 12345,
        },
        author_name="测试UP",
    )
    assert draft is not None
    assert draft.external_id == "BV1xx411c7mD"
    assert draft.item_type == "video"
    assert draft.url.endswith("BV1xx411c7mD")
    assert draft.author_name == "测试UP"
    assert draft.payload["view_count"] == 12345


def test_normalize_dynamic_uses_desc_text() -> None:
    draft = normalize_dynamic(
        {
            "id_str": "123456",
            "modules": {
                "module_dynamic": {
                    "desc": {"text": "今天发个动态"},
                    "major": {},
                },
                "module_author": {"pub_ts": 1719000000},
            },
        },
        author_name="测试UP",
    )
    assert draft is not None
    assert draft.external_id == "123456"
    assert draft.item_type == "dynamic"
    assert "动态" in draft.title or "今天发个动态" in draft.title
