"""B 站订阅同步时段单测。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.jobs.feed.sync_bilibili import is_bilibili_sync_window


def test_bilibili_sync_window_active_during_day() -> None:
    assert is_bilibili_sync_window(datetime(2026, 6, 24, 12, 0, 0)) is True


def test_bilibili_sync_window_inactive_before_8am() -> None:
    assert is_bilibili_sync_window(datetime(2026, 6, 24, 7, 59, 0)) is False


def test_bilibili_sync_window_inactive_from_8pm() -> None:
    assert is_bilibili_sync_window(datetime(2026, 6, 24, 20, 0, 0)) is False
