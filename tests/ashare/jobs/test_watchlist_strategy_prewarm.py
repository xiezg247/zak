"""策略信号磁盘预热任务测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.jobs.watchlist.strategy_prewarm import (
    prewarm_watchlist_strategy_disks,
    warm_watchlist_strategy_cache_job,
)


class WatchlistStrategyPrewarmTests(unittest.TestCase):
    def test_job_skips_without_engine(self) -> None:
        result = warm_watchlist_strategy_cache_job(engine=None)

        self.assertTrue(result.skipped)
        self.assertIn("未就绪", result.message)

    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm.load_signal_panel_symbols", return_value=[])
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm.load_watchlist_signal_config")
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm.load_watchlist_position_config")
    def test_prewarm_skips_when_all_fresh(
        self,
        load_position_config: MagicMock,
        load_signal_config: MagicMock,
        _symbols: MagicMock,
    ) -> None:
        load_signal_config.return_value = WatchlistSignalConfig().normalized()
        load_position_config.return_value.normalized.return_value.effective_signal_config.return_value = (
            WatchlistSignalConfig().normalized()
        )
        engine = MagicMock()
        engine.position_service.get_items.return_value = []

        result = prewarm_watchlist_strategy_disks(engine)

        self.assertTrue(result.skipped)
        engine.analysis_service.batch_strategy_signals.assert_not_called()

    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm.WatchlistPositionDiskCache")
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm.WatchlistSignalDiskCache")
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm._bar_end_date_for", return_value="2026-06-20")
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm._signal_needs_prewarm", return_value=True)
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm._position_needs_prewarm", return_value=False)
    @patch(
        "vnpy_ashare.jobs.watchlist.strategy_prewarm.load_signal_panel_symbols",
        return_value=["600000.SH"],
    )
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm.load_watchlist_signal_config")
    @patch("vnpy_ashare.jobs.watchlist.strategy_prewarm.load_watchlist_position_config")
    def test_prewarm_writes_signal_disk_cache(
        self,
        load_position_config: MagicMock,
        load_signal_config: MagicMock,
        _symbols: MagicMock,
        _position_need: MagicMock,
        _signal_need: MagicMock,
        _bar_end: MagicMock,
        signal_disk_cls: MagicMock,
        position_disk_cls: MagicMock,
    ) -> None:
        config = WatchlistSignalConfig().normalized()
        load_signal_config.return_value = config
        load_position_config.return_value.normalized.return_value.effective_signal_config.return_value = config

        snap = SignalSnapshot(
            vt_symbol="600000.SH",
            strategy_id=config.class_name,
            as_of="2026-06-20",
            signal="hold",
            signal_label="观望",
            signal_date="2026-06-20",
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=50.0,
            reason_summary="测试",
            reasons=(),
            warnings=(),
        )
        engine = MagicMock()
        engine.position_service.get_items.return_value = []
        engine.analysis_service.batch_strategy_signals.return_value = {"600000.SH": snap}
        engine.analysis_service.enrich_relative_index_batch.return_value = {"600000.SH": snap}
        signal_disk = signal_disk_cls.return_value

        result = prewarm_watchlist_strategy_disks(engine)

        self.assertTrue(result.success)
        signal_disk.put_many.assert_called_once()
        position_disk_cls.return_value.put_many.assert_not_called()


if __name__ == "__main__":
    unittest.main()
