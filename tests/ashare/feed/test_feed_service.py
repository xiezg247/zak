"""FeedService 同步单测。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from vnpy_ashare.integrations.bilibili.client import BilibiliClient
from vnpy_ashare.services.feed import run_feed_sync, sync_subscription_record
from vnpy_ashare.storage.repositories import feed as feed_repo


class _FakeClient(BilibiliClient):
    def __init__(self) -> None:
        super().__init__(cookies="SESSDATA=fake")

    @property
    def cookies_configured(self) -> bool:
        return True


@pytest.fixture()
def feed_db(tmp_path, monkeypatch):
    db_path = tmp_path / "feed.db"

    @contextmanager
    def _connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    monkeypatch.setattr(feed_repo, "connect", _connect)
    feed_repo._ensure_schema()
    yield


def test_sync_subscription_inserts_new_video(feed_db, monkeypatch) -> None:
    sub = feed_repo.insert_subscription(
        source_type="bilibili_up",
        source_id="100",
        display_name="UP",
    )
    monkeypatch.setattr(
        "vnpy_ashare.services.feed.list_recent_videos",
        lambda client, mid, count=10: [
            {
                "bvid": "BVNEW",
                "title": "新视频",
                "description": "",
                "created": 2000000000,
                "pic": "",
                "play": 1,
            }
        ],
    )
    monkeypatch.setattr("vnpy_ashare.services.feed.list_recent_dynamics", lambda *args, **kwargs: [])
    result = sync_subscription_record(sub.id, _FakeClient())
    assert result.error == ""
    assert result.new_items == 1


def test_run_feed_sync_skips_when_no_cookie(feed_db, monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.services.feed.BilibiliClient",
        lambda: BilibiliClient(cookies=""),
    )
    result = run_feed_sync()
    assert result.skipped is True
