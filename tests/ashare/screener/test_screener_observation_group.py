"""选股结果加入观察组测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.services.short_term_watchlist import (
    SHORT_TERM_OBSERVATION_GROUP_NAME,
    add_screener_rows_to_short_term_observation_group,
)
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo
from vnpy_ashare.storage.repositories import watchlist_groups as groups_repo


class _WatchlistServiceStub:
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


class TestScreenerObservationGroup(unittest.TestCase):
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

    def test_add_screener_dict_rows(self) -> None:
        rows = [{"vt_symbol": "600519.SSE", "name": "贵州茅台"}]
        result = add_screener_rows_to_short_term_observation_group(self.service, rows)
        self.assertEqual(result.group_added, 1)
        groups = self.service.list_groups()
        self.assertTrue(any(group.name == SHORT_TERM_OBSERVATION_GROUP_NAME for group in groups))
