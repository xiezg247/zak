"""vnpy_tickflow K 线分页测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pandas as pd

import tests._bootstrap  # noqa: F401
from vnpy_tickflow.klines import MAX_BARS_PER_REQUEST, fetch_klines_paged


class KlinesPagedTests(unittest.TestCase):
    def test_single_page(self) -> None:
        client = MagicMock()
        client.klines.get.return_value = pd.DataFrame([{"timestamp": 1000, "open": 1.0}, {"timestamp": 2000, "open": 2.0}])
        df = fetch_klines_paged(client, "600519.SH", "1m", 1000, 5000)
        self.assertEqual(len(df), 2)
        client.klines.get.assert_called_once()

    def test_pagination(self) -> None:
        client = MagicMock()
        page_size = MAX_BARS_PER_REQUEST
        first = pd.DataFrame({"timestamp": range(page_size), "open": [1.0] * page_size})
        second = pd.DataFrame({"timestamp": [page_size, page_size + 1], "open": [2.0, 3.0]})
        client.klines.get.side_effect = [first, second]

        df = fetch_klines_paged(client, "600519.SH", "1d", 0, 999_999_999_999)
        self.assertEqual(len(df), page_size + 2)
        self.assertEqual(client.klines.get.call_count, 2)

    def test_empty_result(self) -> None:
        client = MagicMock()
        client.klines.get.return_value = pd.DataFrame()
        df = fetch_klines_paged(client, "600519.SH", "1d", 0, 1000)
        self.assertTrue(df.empty)


if __name__ == "__main__":
    unittest.main()
