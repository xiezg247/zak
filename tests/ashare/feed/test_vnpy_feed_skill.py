"""vnpy-feed Skill 测试。"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime
from unittest.mock import Mock

import tests._bootstrap  # noqa: F401
from skills.vnpy_feed_skill import VnpyFeedSkill
from vnpy_ashare.domain.feed.models import FeedItemDraft
from vnpy_ashare.services.feed import FeedService
from vnpy_ashare.storage.repositories import feed as feed_repo
from vnpy_common.storage.config import force_database_url, reset_storage_config


class VnpyFeedSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            self.skipTest("需要 DATABASE_URL")
        reset_storage_config()
        force_database_url(url)
        feed_repo.FeedRepository().prepare()

        engine = Mock()
        engine.main_engine = None
        engine.event_engine = None
        engine.notification_service = Mock()
        self.feed_service = FeedService(engine)
        self.skill = VnpyFeedSkill()
        self.skill._services = {"feed": self.feed_service}

        sub = feed_repo.insert_subscription(
            source_type="bilibili_up",
            source_id="123",
            display_name="测试UP",
        )
        feed_repo.insert_items_if_new(
            sub.id,
            sub.source_type,
            [
                FeedItemDraft(
                    external_id="BV1",
                    item_type="video",
                    title="今日视频",
                    summary="",
                    url="https://www.bilibili.com/video/BV1",
                    author_name="测试UP",
                    published_at=datetime.now().isoformat(timespec="seconds"),
                )
            ],
        )

    def tearDown(self) -> None:
        reset_storage_config()

    def test_list_subscriptions(self) -> None:
        payload = json.loads(self.skill.list_feed_subscriptions())
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["subscriptions"][0]["name"], "测试UP")

    def test_get_feed_items(self) -> None:
        payload = json.loads(self.skill.get_feed_items(limit=5))
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["title"], "今日视频")

    def test_check_updated_today(self) -> None:
        payload = json.loads(self.skill.check_bilibili_updated_today())
        self.assertTrue(payload["updated"])
        self.assertEqual(payload["count"], 1)


if __name__ == "__main__":
    unittest.main()
