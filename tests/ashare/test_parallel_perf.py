"""TickFlow 并发拉取与批量回测并行测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy.trader.constant import Exchange

from vnpy_ashare.backtest.batch_runner import batch_backtest_max_workers, resolve_strategy_class
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.quotes.tickflow_client import (
    QUOTE_BATCH_SIZE,
    fetch_quotes_from_tickflow,
    quote_fetch_max_workers,
)
from vnpy_ashare.screener.batch_actions import (
    BatchBacktestParams,
    BatchBacktestRow,
    _batch_row_from_payload,
    run_batch_backtests,
)


class QuoteFetchConcurrencyTests(unittest.TestCase):
    def test_quote_fetch_max_workers_caps_by_batch_count(self) -> None:
        self.assertEqual(quote_fetch_max_workers(batch_count=1), 1)
        self.assertLessEqual(quote_fetch_max_workers(batch_count=20), 8)

    @patch("vnpy_ashare.quotes.tickflow_client.get_tickflow_client")
    def test_fetch_quotes_parallel_batches(self, client_mock: MagicMock) -> None:
        symbols = [f"{index:06d}.SH" for index in range(QUOTE_BATCH_SIZE * 3)]
        items = [StockItem(symbol=f"{index:06d}", exchange=Exchange.SSE, name="") for index in range(len(symbols))]

        def _make_df(batch: list[str]):
            import pandas as pd

            return pd.DataFrame(
                {
                    "symbol": batch,
                    "last_price": [10.0] * len(batch),
                    "prev_close": [9.0] * len(batch),
                    "open": [9.5] * len(batch),
                    "high": [10.5] * len(batch),
                    "low": [9.0] * len(batch),
                    "volume": [1000.0] * len(batch),
                    "amount": [10000.0] * len(batch),
                    "ext.name": [""] * len(batch),
                    "ext.change_pct": [0.01] * len(batch),
                    "ext.change_amount": [0.1] * len(batch),
                    "ext.turnover_rate": [0.02] * len(batch),
                    "ext.amplitude": [0.03] * len(batch),
                }
            )

        client = MagicMock()
        client.quotes.get.side_effect = lambda symbols, as_dataframe=True: _make_df(symbols)
        client_mock.return_value = client

        quotes = fetch_quotes_from_tickflow(items, max_workers=3)
        self.assertEqual(len(quotes), len(symbols))
        self.assertEqual(client.quotes.get.call_count, 3)


class BatchBacktestParallelTests(unittest.TestCase):
    def test_batch_backtest_max_workers(self) -> None:
        self.assertEqual(batch_backtest_max_workers(item_count=1), 1)
        self.assertGreaterEqual(batch_backtest_max_workers(item_count=10), 1)

    def test_resolve_strategy_class(self) -> None:
        cls = resolve_strategy_class("AshareDoubleMaStrategy")
        self.assertEqual(cls.__name__, "AshareDoubleMaStrategy")

    def test_batch_row_from_payload(self) -> None:
        row = _batch_row_from_payload(
            {
                "vt_symbol": "600519.SSE",
                "name": "茅台",
                "total_return": 12.5,
                "error": "",
            }
        )
        self.assertIsInstance(row, BatchBacktestRow)
        self.assertEqual(row.vt_symbol, "600519.SSE")

    @patch("vnpy_ashare.screener.batch_actions.ProcessPoolExecutor")
    @patch("vnpy_ashare.screener.batch_actions.batch_backtest_max_workers", return_value=2)
    def test_run_batch_backtests_uses_process_pool(self, _workers_mock, pool_cls: MagicMock) -> None:
        class _FakeBacktesterEngine:
            pass

        main_engine = MagicMock()
        main_engine.get_engine.return_value = _FakeBacktesterEngine()

        pool = MagicMock()
        pool.__enter__.return_value = pool
        pool.map.return_value = [
            {"vt_symbol": "600519.SSE", "name": "茅台", "error": "", "total_return": 1.0},
            {"vt_symbol": "000001.SZSE", "name": "平安", "error": "", "total_return": 2.0},
        ]
        pool_cls.return_value = pool

        params = BatchBacktestParams(
            class_name="AshareDoubleMaStrategy",
            start=__import__("datetime").datetime(2024, 1, 1),
            end=__import__("datetime").datetime(2024, 6, 1),
        )
        with patch("vnpy_ctabacktester.engine.BacktesterEngine", _FakeBacktesterEngine):
            rows = run_batch_backtests(
                main_engine,
                [
                    {"vt_symbol": "600519.SSE", "name": "茅台"},
                    {"vt_symbol": "000001.SZSE", "name": "平安"},
                ],
                params,
            )
        self.assertEqual(len(rows), 2)
        pool.map.assert_called_once()


if __name__ == "__main__":
    unittest.main()
