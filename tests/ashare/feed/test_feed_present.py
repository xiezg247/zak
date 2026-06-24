"""信息流展示辅助单测。"""

from vnpy_ashare.domain.feed.models import FeedItem
from vnpy_ashare.domain.feed.present import (
    feed_item_detail_text,
    feed_item_meta_text,
    feed_item_title_text,
)


def _item(**kwargs) -> FeedItem:
    defaults = {
        "id": "1",
        "subscription_id": "sub",
        "source_type": "bilibili_up",
        "external_id": "x",
        "author_name": "UP",
        "item_type": "video",
        "title": "标题",
        "summary": "",
        "url": "https://bilibili.com",
        "published_at": "2026-06-23T12:00:00",
        "payload": {},
        "created_at": "2026-06-23T12:00:00",
    }
    defaults.update(kwargs)
    return FeedItem(**defaults)


def test_title_and_detail_for_video() -> None:
    item = _item(summary="简介正文", title="视频标题")
    assert feed_item_title_text(item) == "视频标题"
    assert feed_item_detail_text(item) == "简介正文"


def test_title_uses_first_line_for_generic_dynamic() -> None:
    item = _item(item_type="dynamic", title="新动态", summary="第一行\n第二行详情")
    assert feed_item_title_text(item) == "第一行"
    assert feed_item_detail_text(item) == "第二行详情"


def test_image_dynamic_splits_title_and_detail() -> None:
    item = _item(
        item_type="dynamic",
        title="图片动态（1 张）",
        summary="图片动态（1 张）",
        payload={"dynamic_type": "DYNAMIC_TYPE_DRAW", "cover_url": "http://example.com/a.jpg"},
    )
    assert feed_item_title_text(item) == "图片动态"
    assert "共 1 张图片" in feed_item_detail_text(item)


def test_empty_draw_dynamic_shows_hint() -> None:
    item = _item(
        item_type="dynamic",
        title="新动态",
        summary="",
        payload={"dynamic_type": "DYNAMIC_TYPE_DRAW"},
    )
    assert feed_item_title_text(item) == "图片动态"
    assert "无文字说明" in feed_item_detail_text(item)


def test_meta_includes_view_count() -> None:
    item = _item(payload={"view_count": 99})
    assert "播放 99" in feed_item_meta_text(item)
