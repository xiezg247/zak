"""vnpy-watchlist get_short_term_watchlist 测试。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from skills.vnpy_watchlist_skill import VnpyWatchlistSkill
from vnpy_ashare.quotes.radar.radar_models import RadarResonanceEntry
from vnpy_ashare.quotes.radar.radar_resonance_store import set_radar_resonance_entries
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo
from vnpy_ashare.storage.repositories import watchlist_groups as groups_repo


class _WatchlistServiceStub:
    def get_items(self):
        return [{"symbol": symbol, "exchange": exchange.value, "name": name} for symbol, exchange, name in watchlist_repo.load_watchlist_rows()]

    def list_groups(self):
        return groups_repo.load_watchlist_groups()

    def create_group(self, name: str):
        return groups_repo.create_watchlist_group(name)

    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool:
        return watchlist_repo.add_watchlist_item(symbol, exchange, name)

    def add_failure_reason(self, symbol: str, exchange: Exchange):
        return watchlist_repo.watchlist_add_failure_reason(symbol, exchange)

    def add_to_group(self, group_id: str, symbol: str, exchange: Exchange) -> bool:
        return groups_repo.add_watchlist_group_member(group_id, symbol, exchange)

    def group_member_keys(self, group_id: str):
        return groups_repo.load_watchlist_group_member_keys(group_id)


class TestGetShortTermWatchlistSkill(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()
        watchlist_repo.add_watchlist_item("600519", Exchange.SSE, "贵州茅台")
        group_id = groups_repo.create_watchlist_group("短线观察")
        assert group_id
        groups_repo.add_watchlist_group_member(group_id, "600519", Exchange.SSE)
        set_radar_resonance_entries(
            (
                RadarResonanceEntry(
                    vt_symbol="600519.SSE",
                    name="贵州茅台",
                    symbol="600519",
                    card_count=2,
                    card_titles=("选股·龙头",),
                    price=1800.0,
                    change_pct=3.0,
                    resonance_score=5.0,
                ),
            )
        )
        self.skill = VnpyWatchlistSkill()
        self.skill._services = {"watchlist": _WatchlistServiceStub()}

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_get_short_term_watchlist(self) -> None:
        raw = self.skill.get_short_term_watchlist(resonance_top_n=5)
        payload = json.loads(raw)
        self.assertEqual(payload["observation_count"], 1)
        self.assertEqual(payload["observation_symbols"][0]["symbol"], "600519")
        self.assertEqual(payload["resonance_symbols"][0]["vt_symbol"], "600519.SSE")
