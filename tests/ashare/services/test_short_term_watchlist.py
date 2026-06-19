"""短线工作流：自选池批量写入与 AI 快照测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData, RadarRow
from vnpy_ashare.services.watchlist_short_term import (
    add_rows_to_watchlist_pool,
    add_screener_rows_to_watchlist_pool,
    collect_dragon_1_rows,
)
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo


def _row(vt_symbol: str, *, tier: str = "") -> RadarRow:
    symbol = vt_symbol.split(".")[0]
    return RadarRow(
        vt_symbol=vt_symbol,
        name=symbol,
        symbol=symbol,
        price=10.0,
        change_pct=5.0,
        metric_label="",
        metric_value="",
        sub_label="",
        sub_value="",
        leader_tier=tier,
    )


class _WatchlistServiceStub:
    def get_items(self):
        return [
            {"symbol": symbol, "exchange": exchange.value, "name": name}
            for symbol, exchange, name in watchlist_repo.load_watchlist_rows()
        ]

    def list_groups(self):
        return []

    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool:
        return watchlist_repo.add_watchlist_item(symbol, exchange, name)

    def add_failure_reason(self, symbol: str, exchange: Exchange):
        return watchlist_repo.watchlist_add_failure_reason(symbol, exchange)


class TestShortTermWatchlist(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()
        self.service = _WatchlistServiceStub()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_add_rows_to_watchlist_pool(self) -> None:
        rows = (_row("600519.SSE"), _row("000001.SZSE"))
        result = add_rows_to_watchlist_pool(self.service, rows)
        self.assertEqual(result.watchlist_added, 2)
        self.assertEqual(result.skipped, 0)
        self.assertTrue(watchlist_repo.watchlist_contains("600519", Exchange.SSE))

    def test_add_screener_rows_to_watchlist_pool(self) -> None:
        rows = [{"vt_symbol": "600519.SSE", "name": "贵州茅台"}]
        result = add_screener_rows_to_watchlist_pool(self.service, rows)
        self.assertEqual(result.watchlist_added, 1)
        self.assertTrue(watchlist_repo.watchlist_contains("600519", Exchange.SSE))

    def test_collect_dragon_1_rows(self) -> None:
        payload = {
            "leader_pick": RadarCardData(
                card_id="leader_pick",
                title="龙头",
                subtitle="",
                rows=(
                    _row("600519.SSE", tier="dragon_1"),
                    _row("000001.SZSE", tier="dragon_2"),
                ),
                empty_message="",
                updated_at="",
            )
        }
        dragons = collect_dragon_1_rows(payload)
        self.assertEqual(len(dragons), 1)
        self.assertEqual(dragons[0].vt_symbol, "600519.SSE")

    def test_build_short_term_watchlist_snapshot(self) -> None:
        from vnpy_ashare.config.preferences.watchlist_signal import save_signal_panel_symbols
        from vnpy_ashare.quotes.radar.radar_models import RadarResonanceEntry
        from vnpy_ashare.quotes.radar.radar_resonance_store import set_radar_resonance_entries
        from vnpy_ashare.services.watchlist_short_term import build_short_term_watchlist_snapshot

        watchlist_repo.add_watchlist_item("600519", Exchange.SSE, "贵州茅台")
        save_signal_panel_symbols(["600519.SSE"])

        set_radar_resonance_entries(
            (
                RadarResonanceEntry(
                    vt_symbol="000001.SZSE",
                    name="平安银行",
                    symbol="000001",
                    card_count=3,
                    card_titles=("发现·放量", "板块·主线"),
                    price=10.0,
                    change_pct=5.0,
                    resonance_score=4.5,
                ),
            )
        )
        snapshot = build_short_term_watchlist_snapshot(self.service, resonance_top_n=3)
        self.assertEqual(snapshot["signal_panel_count"], 1)
        self.assertEqual(len(snapshot["resonance_symbols"]), 1)
        self.assertEqual(snapshot["resonance_symbols"][0]["vt_symbol"], "000001.SZSE")
