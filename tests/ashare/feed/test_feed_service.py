"""FeedService 同步单测。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vnpy_ashare.domain.feed.models import FeedSubscriptionConfig
from vnpy_ashare.integrations.bilibili.client import BilibiliClient
from vnpy_ashare.services.feed import FeedService, run_feed_sync, sync_subscription_record
from vnpy_ashare.storage.repositories import feed as feed_repo


class _FakeClient(BilibiliClient):
    def __init__(self) -> None:
        super().__init__(cookies="SESSDATA=fake")

    @property
    def cookies_configured(self) -> bool:
        return True


@pytest.fixture()
def feed_db(pg_storage):
    _ = pg_storage
    feed_repo._ensure_schema()
    yield


def test_sync_subscription_inserts_new_dynamic(feed_db, monkeypatch) -> None:
    sub = feed_repo.insert_subscription(
        source_type="bilibili_up",
        source_id="100",
        display_name="UP",
    )
    monkeypatch.setattr(
        "vnpy_ashare.services.feed.list_recent_dynamics",
        lambda client, mid, **kwargs: [
            {
                "id_str": "999",
                "modules": {
                    "module_dynamic": {
                        "desc": {"text": "测试动态"},
                        "major": {},
                    },
                    "module_author": {"pub_ts": 2000000000},
                },
            }
        ],
    )
    monkeypatch.setattr("vnpy_ashare.services.feed.get_dynamic_detail", lambda *args, **kwargs: None)
    result = sync_subscription_record(sub.id, _FakeClient())
    assert result.error == ""
    assert result.new_items == 1


def test_add_bilibili_up_by_keyword(feed_db, monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.services.feed.search_users",
        lambda client, keyword, **kwargs: [{"mid": "123", "name": "测试UP", "avatar": "https://example.com/a.jpg"}],
    )
    service = FeedService(MagicMock())
    service.set_client_factory(_FakeClient)
    sub = service.add_bilibili_up(keyword="测试UP", config=FeedSubscriptionConfig(), sync_now=False)
    assert sub.source_id == "123"
    assert sub.display_name == "测试UP"


def test_run_feed_sync_skips_when_no_cookie(feed_db, monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.services.feed.BilibiliClient",
        lambda: BilibiliClient(cookies=""),
    )
    result = run_feed_sync()
    assert result.skipped is True
