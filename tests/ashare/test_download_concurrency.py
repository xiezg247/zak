"""下载并发与表格索引测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.config.constants.concurrency import (
    CAP_MCP_INTRADAY_FLOW_MAX_WORKERS,
    ENV_MCP_INTRADAY_FLOW_MAX_WORKERS,
)
from vnpy_ashare.data.download_concurrency import (
    download_max_workers,
    env_max_workers,
    mcp_intraday_flow_max_workers,
    run_parallel_map,
)


class DownloadConcurrencyTests(unittest.TestCase):
    def test_download_max_workers(self) -> None:
        self.assertEqual(download_max_workers(item_count=1), 1)
        self.assertGreaterEqual(download_max_workers(item_count=10), 1)

    def test_run_parallel_map_preserves_order(self) -> None:
        items = list(range(6))
        results = run_parallel_map(items, lambda value: value * 2, max_workers=2)
        self.assertEqual(results, [0, 2, 4, 6, 8, 10])

    def test_run_parallel_map_allows_none_results(self) -> None:
        items = [1, 2, 3, 4]

        def worker(value: int) -> int | None:
            return None if value % 2 == 0 else value

        results = run_parallel_map(items, worker, max_workers=2)
        self.assertEqual(results, [1, None, 3, None])

    def test_env_max_workers_reads_environment(self) -> None:
        with patch.dict("os.environ", {ENV_MCP_INTRADAY_FLOW_MAX_WORKERS: "6"}, clear=False):
            self.assertEqual(mcp_intraday_flow_max_workers(item_count=10), 6)
            self.assertEqual(mcp_intraday_flow_max_workers(item_count=3), 3)
        self.assertEqual(mcp_intraday_flow_max_workers(item_count=99), 4)

    def test_env_max_workers_respects_cap(self) -> None:
        with patch.dict("os.environ", {ENV_MCP_INTRADAY_FLOW_MAX_WORKERS: "99"}):
            self.assertEqual(
                mcp_intraday_flow_max_workers(item_count=20),
                CAP_MCP_INTRADAY_FLOW_MAX_WORKERS,
            )

    def test_env_max_workers_invalid_value_falls_back(self) -> None:
        with patch.dict("os.environ", {ENV_MCP_INTRADAY_FLOW_MAX_WORKERS: "bad"}):
            workers = env_max_workers(
                ENV_MCP_INTRADAY_FLOW_MAX_WORKERS,
                4,
                item_count=8,
                cap=CAP_MCP_INTRADAY_FLOW_MAX_WORKERS,
            )
        self.assertEqual(workers, 4)

    @patch("vnpy_ashare.jobs.bars.local_fill.download_bars", return_value=1)
    def test_batch_fill_stale_parallel(self, _mock) -> None:
        from datetime import datetime

        from vnpy.trader.constant import Exchange

        from vnpy_ashare.data.bar_health import BarMeta
        from vnpy_ashare.domain.symbols.stock import StockItem
        from vnpy_ashare.jobs.bars.local_fill import batch_fill_stale_daily_bars

        items = [
            StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台"),
            StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安"),
        ]
        meta = {
            (items[0].symbol, items[0].exchange): BarMeta(
                start=datetime(2026, 5, 1),
                end=datetime(2026, 5, 30),
                count=20,
            ),
            (items[1].symbol, items[1].exchange): BarMeta(
                start=datetime(2026, 5, 1),
                end=datetime(2026, 5, 30),
                count=20,
            ),
        }
        result = batch_fill_stale_daily_bars(
            items,
            meta,
            delay=0,
            end=datetime(2026, 6, 5),
            max_workers=2,
        )
        self.assertEqual(result.success, 2)
        self.assertEqual(_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
