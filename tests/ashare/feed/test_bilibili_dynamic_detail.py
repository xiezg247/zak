"""动态详情补全单测。"""

from __future__ import annotations

from vnpy_ashare.domain.feed.models import FeedItemDraft
from vnpy_ashare.integrations.bilibili.normalize import (
    dynamic_needs_detail_fetch,
    merge_dynamic_drafts,
    normalize_dynamic,
)


def test_dynamic_needs_detail_when_summary_empty() -> None:
    draft = FeedItemDraft(
        external_id="1",
        item_type="dynamic",
        title="新动态",
        summary="",
        url="https://t.bilibili.com/1",
        author_name="UP",
        published_at="2026-06-23T12:00:00",
    )
    assert dynamic_needs_detail_fetch(draft) is True


def test_merge_prefers_detail_summary() -> None:
    base = FeedItemDraft(
        external_id="1",
        item_type="dynamic",
        title="新动态",
        summary="",
        url="https://t.bilibili.com/1",
        author_name="UP",
        published_at="2026-06-23T12:00:00",
        payload={"cover_url": "http://a"},
    )
    detail = FeedItemDraft(
        external_id="1",
        item_type="dynamic",
        title="新动态",
        summary="详情正文",
        url="https://t.bilibili.com/1",
        author_name="UP",
        published_at="2026-06-23T12:00:00",
        payload={},
    )
    merged = merge_dynamic_drafts(base, detail)
    assert merged.summary == "详情正文"
    assert merged.title == "详情正文"
    assert merged.payload["cover_url"] == "http://a"


def test_normalize_draw_with_rich_text_desc() -> None:
    draft = normalize_dynamic(
        {
            "id_str": "123",
            "type": "DYNAMIC_TYPE_DRAW",
            "modules": {
                "module_dynamic": {
                    "desc": {
                        "rich_text_nodes": [
                            {
                                "orig_text": "今日观点",
                                "text": "今日观点",
                                "type": "RICH_TEXT_NODE_TYPE_TEXT",
                            }
                        ],
                        "text": "",
                    },
                    "major": {
                        "draw": {
                            "items": [{"src": "http://img"}],
                        },
                        "type": "MAJOR_TYPE_DRAW",
                    },
                },
                "module_author": {"pub_ts": 1719000000},
            },
        },
        author_name="UP",
    )
    assert draft is not None
    assert draft.summary == "今日观点"
    assert draft.title == "今日观点"
