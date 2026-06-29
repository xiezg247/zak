"""feed repository 单测。"""

from __future__ import annotations

import pytest

from vnpy_ashare.domain.feed.models import FeedItemDraft, FeedSubscriptionConfig
from vnpy_ashare.storage.repositories import feed as feed_repo


@pytest.fixture()
def feed_db(pg_storage):
    _ = pg_storage
    feed_repo.FeedRepository().prepare()
    yield


def test_insert_subscription_and_dedupe_items(feed_db) -> None:
    sub = feed_repo.insert_subscription(
        source_type="bilibili_up",
        source_id="12345",
        display_name="UP主A",
    )
    draft = FeedItemDraft(
        external_id="BV123",
        item_type="video",
        title="标题",
        summary="",
        url="https://www.bilibili.com/video/BV123",
        author_name="UP主A",
        published_at="2026-06-23T10:00:00",
    )
    first = feed_repo.insert_items_if_new(sub.id, sub.source_type, [draft])
    second = feed_repo.insert_items_if_new(sub.id, sub.source_type, [draft])
    assert len(first) == 1
    assert len(second) == 0
    assert feed_repo.count_unread() == 1

    feed_repo.mark_read([first[0].id])
    assert feed_repo.count_unread() == 0


def test_update_subscription_config(feed_db) -> None:
    sub = feed_repo.insert_subscription(
        source_type="bilibili_up",
        source_id="999",
        display_name="UP主B",
        config=FeedSubscriptionConfig(dynamics=False),
    )
    feed_repo.update_subscription(sub.id, enabled=False)
    loaded = feed_repo.get_subscription(sub.id)
    assert loaded is not None
    assert loaded.enabled is False
