"""ScreeningService 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401

from vnpy_ashare.services.screening_service import ScreeningService


class ScreeningServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MagicMock()
        self.engine.quote_service = MagicMock()
        self.service = ScreeningService(self.engine)

    def test_load_quote_rows_from_cache(self) -> None:
        rows = [{"symbol": "600519", "change_pct": 1.2}]
        self.engine.quote_service.get_market_quotes_cache.return_value = rows
        loaded, err = self.service.load_quote_rows()
        self.assertEqual(loaded, rows)
        self.assertIsNone(err)

    def test_load_quote_rows_from_redis_when_cache_empty(self) -> None:
        snapshot = MagicMock()
        snapshot.rows = [{"symbol": "000001", "change_pct": -0.5}]
        self.engine.quote_service.get_market_quotes_cache.return_value = []
        with patch(
            "vnpy_ashare.screener.quotes_loader.load_market_quote_rows",
            return_value=snapshot,
        ):
            loaded, err = self.service.load_quote_rows()
        self.assertEqual(loaded, snapshot.rows)
        self.assertIsNone(err)

    def test_screen_quote_preset_without_data(self) -> None:
        with patch.object(
            self.service,
            "load_quote_rows",
            return_value=(None, "Redis 不可用"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                self.service.screen_quote_preset("涨幅榜")
        self.assertIn("行情采集", str(ctx.exception))

    def test_screen_quote_preset_delegates_to_rules(self) -> None:
        rows = [{"symbol": "600519", "change_pct": 5.0}]
        with patch.object(self.service, "load_quote_rows", return_value=(rows, None)), patch(
            "vnpy_ashare.screener.rules.apply_quote_preset",
            return_value=[{"symbol": "600519"}],
        ) as mock_apply:
            result = self.service.screen_quote_preset("涨幅榜", top_n=3)
        mock_apply.assert_called_once_with("涨幅榜", rows, top_n=3)
        self.assertEqual(result, [{"symbol": "600519"}])


if __name__ == "__main__":
    unittest.main()
