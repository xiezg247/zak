"""形态选股执行单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.screener.pattern_rules import BarSeries
from vnpy_ashare.screener.pattern_screen import (
    PatternScreenInput,
    normalize_pattern_id,
    resolve_pattern_screen,
    run_pattern_screen,
)


def _rising_series(count: int) -> BarSeries:
    closes = [100.0 + index * 0.8 for index in range(count)]
    return BarSeries(
        closes=closes,
        highs=[value + 1 for value in closes],
        lows=[value - 1 for value in closes],
        volumes=[1000.0 + index * 10 for index in range(count)],
    )


class PatternScreenTests(unittest.TestCase):
    def test_normalize_pattern_aliases(self) -> None:
        self.assertEqual(normalize_pattern_id("老鸭头形态"), "old_duck")
        self.assertEqual(normalize_pattern_id("W底"), "w_bottom")
        self.assertEqual(normalize_pattern_id("主题投资"), "theme_hot")
        self.assertEqual(normalize_pattern_id("未知形态"), "")

    def test_resolve_pattern_screen_unknown(self) -> None:
        pattern_id, error = resolve_pattern_screen(PatternScreenInput(pattern="未知"))
        self.assertEqual(pattern_id, "")
        self.assertIn("未知形态", error)

    def test_run_pattern_screen_bar_mode(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        series = _rising_series(80)

        def _load_bars(symbol: str, exchange: Exchange) -> list:
            _ = symbol, exchange
            from datetime import datetime, timedelta

            from vnpy.trader.constant import Interval
            from vnpy.trader.object import BarData

            bars = []
            anchor = datetime(2024, 1, 1, 15, 0, 0)
            for index, close in enumerate(series.closes):
                bars.append(
                    BarData(
                        symbol=item.symbol,
                        exchange=item.exchange,
                        datetime=anchor + timedelta(days=index),
                        interval=Interval.DAILY,
                        open_price=close,
                        high_price=close + 1,
                        low_price=close - 1,
                        close_price=close,
                        volume=series.volumes[index],
                        gateway_name="TEST",
                    )
                )
            return bars

        with patch(
            "vnpy_ashare.screener.pattern_screen.load_downloaded_stocks",
            return_value=[item],
        ):
            result = run_pattern_screen(
                "ma_bull",
                top_n=5,
                load_bars=_load_bars,
            )
        self.assertEqual(result.source, "bar")
        self.assertIn("均线多头", result.condition)
        self.assertGreaterEqual(result.total_scanned, 1)

    def test_run_pattern_screen_theme_hot(self) -> None:
        quote_rows = [
            {
                "symbol": "000001",
                "name": "平安银行",
                "vt_symbol": "000001.SZSE",
                "change_pct": 5.0,
                "turnover_rate": 4.0,
            },
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "vt_symbol": "600519.SSE",
                "change_pct": 1.0,
                "turnover_rate": 1.0,
            },
        ]
        result = run_pattern_screen(
            "theme_hot",
            top_n=1,
            load_bars=lambda *_args, **_kwargs: [],
            quote_rows=quote_rows,
        )
        self.assertEqual(result.source, "quote")
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["symbol"], "000001")


if __name__ == "__main__":
    unittest.main()
