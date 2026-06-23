"""信息流 AI 上下文测试。"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ai.context.feed import format_feed_page_extra
from vnpy_ashare.domain.feed.models import FeedItemDraft
from vnpy_ashare.services.feed import FeedService
from vnpy_ashare.storage.repositories import feed as feed_repo


class FeedContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)

        @contextmanager
        def _connect():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

        self._patcher = patch.object(feed_repo, "connect", _connect)
        self._patcher.start()
        feed_repo._ensure_schema()
        engine = Mock(notification_service=Mock())
        self.feed_service = FeedService(engine)
        sub = feed_repo.insert_subscription(
            source_type="bilibili_up",
            source_id="1",
            display_name="老番茄",
        )
        feed_repo.insert_items_if_new(
            sub.id,
            sub.source_type,
            [
                FeedItemDraft(
                    external_id="BV9",
                    item_type="video",
                    title="新视频",
                    summary="",
                    url="https://example.com",
                    author_name="老番茄",
                    published_at="2026-06-23T12:00:00",
                )
            ],
        )

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_format_feed_page_extra_lists_unread(self) -> None:
        text = format_feed_page_extra(self.feed_service)
        self.assertIn("未读 1", text)
        self.assertIn("老番茄", text)
        self.assertIn("新视频", text)


if __name__ == "__main__":
    unittest.main()
