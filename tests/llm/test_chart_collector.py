"""迷你图工具结果解析测试。"""

from __future__ import annotations

import json
import unittest

import pandas as pd

from vnpy_ashare.backtest.equity_curve import sample_equity_curve
from vnpy_common.ai.protocol import AiChartSpec
from vnpy_llm.tools.chart_collector import attachment_key, merge_chart_attachment, try_collect_chart, try_collect_charts


class ChartCollectorTests(unittest.TestCase):
    def test_collect_candlestick_from_get_bars_data(self) -> None:
        payload = {
            "symbol": "600519.SSE",
            "scope": "daily",
            "count": 2,
            "data": [
                {
                    "date": "2026-06-23",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "volume": 1000,
                },
                {
                    "date": "2026-06-24",
                    "open": 10.5,
                    "high": 11.2,
                    "low": 10.1,
                    "close": 10.2,
                    "volume": 900,
                },
            ],
        }
        spec = try_collect_chart("get_bars_data", json.dumps(payload, ensure_ascii=False), success=True)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.kind, "candlestick")
        self.assertEqual(spec.symbol, "600519.SSE")
        self.assertEqual(len(spec.series), 2)
        self.assertGreaterEqual(len(spec.overlays), 2)
        self.assertIn("600519.SSE", spec.caption)

    def test_collect_candlestick_from_technical_snapshot(self) -> None:
        payload = {
            "symbol": "600519.SSE",
            "name": "贵州茅台",
            "scope": "daily",
            "chart_series": [
                {
                    "date": "2026-06-24",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "volume": 1000,
                }
            ],
        }
        spec = try_collect_chart("technical_snapshot", json.dumps(payload, ensure_ascii=False), success=True)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.name, "贵州茅台")
        self.assertIn("技术面", spec.caption)

    def test_collect_line_from_backtest_result(self) -> None:
        payload = {
            "strategy": "双均线",
            "vt_symbol": "600519.SSE",
            "equity_curve": [
                {"date": "2026-01-02", "value": 1000000},
                {"date": "2026-06-24", "value": 1120000},
            ],
        }
        spec = try_collect_chart("get_backtest_result", json.dumps(payload, ensure_ascii=False), success=True)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.kind, "line")
        self.assertEqual(spec.chart_key, "backtest:600519.SSE")

    def test_collect_skips_error_payload(self) -> None:
        raw = json.dumps({"error": "无法解析代码: foo"}, ensure_ascii=False)
        self.assertIsNone(try_collect_chart("get_bars_data", raw, success=True))

    def test_collect_skips_failed_tool(self) -> None:
        raw = json.dumps({"symbol": "600519.SSE", "data": []}, ensure_ascii=False)
        self.assertIsNone(try_collect_chart("get_bars_data", raw, success=False))

    def test_merge_dedupes_symbol(self) -> None:
        first = AiChartSpec(
            chart_id="a1",
            kind="candlestick",
            symbol="600519.SSE",
            series=[],
        )
        second = AiChartSpec(
            chart_id="a2",
            kind="candlestick",
            symbol="600519.SSE",
            series=[],
        )
        merged = merge_chart_attachment([first], second)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].chart_id, "a2")

    def test_merge_keeps_stock_and_backtest_charts(self) -> None:
        stock = AiChartSpec(
            chart_id="s1",
            kind="candlestick",
            symbol="600519.SSE",
            series=[],
        )
        backtest = AiChartSpec(
            chart_id="b1",
            kind="line",
            symbol="600519.SSE",
            chart_key="backtest:600519.SSE",
            series=[],
        )
        merged = merge_chart_attachment([stock], backtest)
        self.assertEqual(len(merged), 2)
        self.assertEqual(attachment_key(stock), "600519.SSE")
        self.assertEqual(attachment_key(backtest), "backtest:600519.SSE")


class ScreeningChartTests(unittest.TestCase):
    def test_collect_screening_batch_charts(self) -> None:
        payload = {
            "count": 2,
            "batch_snapshots": [
                {
                    "vt_symbol": "600519.SSE",
                    "name": "贵州茅台",
                    "chart_series": [
                        {
                            "date": "2026-06-24",
                            "open": 10,
                            "high": 11,
                            "low": 9,
                            "close": 10.5,
                            "volume": 100,
                        }
                    ],
                },
                {
                    "vt_symbol": "000001.SZSE",
                    "name": "平安银行",
                    "chart_series": [
                        {
                            "date": "2026-06-24",
                            "open": 12,
                            "high": 13,
                            "low": 11,
                            "close": 12.5,
                            "volume": 200,
                        }
                    ],
                },
            ],
        }
        charts = try_collect_charts(
            "explain_screening_run",
            json.dumps(payload, ensure_ascii=False),
            success=True,
        )
        self.assertEqual(len(charts), 2)
        self.assertIn("选股Top", charts[0].caption)


class EquityCurveSampleTests(unittest.TestCase):
    def test_sample_equity_curve(self) -> None:
        index = pd.date_range("2026-01-01", periods=120, freq="D")
        df = pd.DataFrame({"balance": range(1_000_000, 1_000_120)}, index=index)
        rows = sample_equity_curve(df, max_points=10)
        self.assertGreaterEqual(len(rows), 2)
        self.assertLessEqual(len(rows), 10)
        self.assertIn("date", rows[0])
        self.assertIn("value", rows[0])


if __name__ == "__main__":
    unittest.main()
