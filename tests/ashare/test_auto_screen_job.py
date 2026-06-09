"""定时自动选股任务测试。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from vnpy_ashare.jobs.auto_screen import run_scheduled_auto_screen
from vnpy_ashare.screener.runner import ScreenerRunResult


def test_screen_intraday_skips_off_hours():
    next_run = datetime(2026, 6, 10, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    with patch(
        "vnpy_ashare.jobs.auto_screen.is_ashare_trading_session",
        return_value=False,
    ):
        with patch(
            "vnpy_ashare.jobs.auto_screen.next_quotes_collect_at",
            return_value=next_run,
        ):
            result = run_scheduled_auto_screen("screen_intraday", force=False)

    assert result.skipped is True
    assert "非交易时段" in result.message


def test_screen_intraday_force_runs():
    fake_result = ScreenerRunResult(
        rows=[{"vt_symbol": "600000.SSE", "name": "浦发银行", "composite_score": 88}],
        condition="自动 · 盘中多因子",
        updated_at="2026-06-09 10:00:00",
        total_scanned=100,
        source="recipe",
    )
    with patch(
        "vnpy_ashare.jobs.auto_screen.is_ashare_trading_session",
        return_value=False,
    ):
        with patch(
            "vnpy_ashare.jobs.auto_screen.run_recipe",
            return_value=fake_result,
        ):
            with patch("vnpy_ashare.jobs.auto_screen.persist_scheduled_recipe_run"):
                result = run_scheduled_auto_screen("screen_intraday", force=True)

    assert result.success is True
    assert not result.skipped


def test_screen_post_close_skips_before_close():
    noon = datetime(2026, 6, 9, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    with patch("vnpy_ashare.jobs.auto_screen.datetime") as mock_dt:
        mock_dt.now.return_value = noon
        with patch(
            "vnpy_ashare.jobs.auto_screen.is_trading_day",
            return_value=True,
        ):
            result = run_scheduled_auto_screen("screen_post_close", force=False)

    assert result.skipped is True
    assert "尚未收盘" in result.message
