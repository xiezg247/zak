"""行情 Hub 与采集部署模式测试。"""

from __future__ import annotations

import os
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.screener.quotes_snapshot import MarketQuotesSnapshot
from vnpy_ashare.quotes.core.collect_mode import (
    quote_collect_external_enabled,
    scheduler_collect_quotes_enabled,
)
from vnpy_ashare.quotes.core.market_snapshot_hub import (
    clear_process_quote_snapshot,
    get_process_quote_snapshot,
    publish_market_snapshot,
)
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache


def test_publish_market_snapshot_syncs_row_cache() -> None:
    clear_process_quote_snapshot()
    snapshot = MarketQuotesSnapshot(
        rows=[{"vt_symbol": "600000.SH", "change_pct": 1.0}],
        updated_at="2026-06-27",
        total=1,
        source="test",
    )
    with patch("vnpy_ashare.quotes.core.market_snapshot_hub.seq_matches", return_value=True):
        publish_market_snapshot(snapshot)
        assert get_process_quote_snapshot() is snapshot
    assert len(get_market_quotes_cache()) == 1


def test_external_collect_mode_skips_scheduler_collect() -> None:
    prev = os.environ.get("ZAK_QUOTE_COLLECT_MODE")
    os.environ["ZAK_QUOTE_COLLECT_MODE"] = "external"
    try:
        assert quote_collect_external_enabled()
        assert not scheduler_collect_quotes_enabled()
    finally:
        if prev is None:
            os.environ.pop("ZAK_QUOTE_COLLECT_MODE", None)
        else:
            os.environ["ZAK_QUOTE_COLLECT_MODE"] = prev


def test_scheduler_collect_quotes_skipped_when_external() -> None:
    from vnpy_ashare.scheduler.manager import TaskSchedulerManager

    prev = os.environ.get("ZAK_QUOTE_COLLECT_MODE")
    os.environ["ZAK_QUOTE_COLLECT_MODE"] = "external"
    try:
        manager = TaskSchedulerManager()
        with patch.object(manager, "_get_job_config") as get_cfg:
            get_cfg.return_value.enabled = True
            with patch.object(manager._scheduler, "add_job") as add_job:
                manager._schedule_collect_quotes()
                add_job.assert_not_called()
    finally:
        if prev is None:
            os.environ.pop("ZAK_QUOTE_COLLECT_MODE", None)
        else:
            os.environ["ZAK_QUOTE_COLLECT_MODE"] = prev
