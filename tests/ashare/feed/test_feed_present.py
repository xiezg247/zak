"""信息流展示辅助单测。"""

from vnpy_ashare.domain.feed.models import FeedItem
from vnpy_ashare.domain.feed.present import feed_item_detail_text, feed_item_meta_text


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


def test_detail_prefers_summary_over_title() -> None:
    item = _item(summary="简介正文", title="标题")
    assert feed_item_detail_text(item) == "简介正文"


def test_detail_hides_summary_when_same_as_title() -> None:
    item = _item(summary="标题", title="标题", payload={"view_count": 1200})
    assert feed_item_detail_text(item) == "播放 1,200"


def test_meta_includes_view_count() -> None:
    item = _item(payload={"view_count": 99})
    assert "播放 99" in feed_item_meta_text(item)
