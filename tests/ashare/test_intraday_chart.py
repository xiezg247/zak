"""分时图数据映射与均价计算测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData
from vnpy.trader.utility import ZoneInfo

from vnpy_ashare.market_hours import (
    INTRADAY_SESSION_MINUTES,
    MORNING_SESSION_MINUTES,
    bar_session_minute,
    session_minute_to_time_label,
    vwap_price,
)
from vnpy_ashare.ui.chart_style import FALL_RGB, RISE_RGB
from vnpy_ashare.ui.intraday_chart import (
    build_price_segments,
    calc_intraday_avg_prices,
    format_intraday_summary,
    format_pct_tick,
    format_volume_lots,
    nearest_bar_index,
    pct_change,
    price_y_range,
    session_x_values,
    volume_bar_color,
    volume_y_range,
)

CHINA_TZ = ZoneInfo("Asia/Shanghai")


def _bar(
    hour: int,
    minute: int,
    *,
    close: float,
    volume: float,
    amount: float,
) -> BarData:
    return BarData(
        symbol="600519",
        exchange=Exchange.SSE,
        datetime=datetime(2026, 6, 8, hour, minute, tzinfo=CHINA_TZ),
        interval=Interval.MINUTE,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=volume,
        turnover=amount,
        gateway_name="TEST",
    )


class VwapTests(unittest.TestCase):
    def test_vwap_uses_lot_size(self) -> None:
        # 90 手 × 100 股，成交额 11401642 元 → 均价约 1266.85
        self.assertAlmostEqual(vwap_price(11_401_642.0, 90.0), 1266.849111, places=3)


class SessionLabelTests(unittest.TestCase):
    def test_session_minute_to_time_label_morning(self) -> None:
        self.assertEqual(session_minute_to_time_label(0.0), "09:30")
        self.assertEqual(session_minute_to_time_label(60.0), "10:30")

    def test_session_minute_to_time_label_afternoon(self) -> None:
        self.assertEqual(
            session_minute_to_time_label(float(MORNING_SESSION_MINUTES)),
            "13:00",
        )
        self.assertEqual(
            session_minute_to_time_label(float(INTRADAY_SESSION_MINUTES)),
            "15:00",
        )


class SessionMinuteTests(unittest.TestCase):
    def test_morning_open(self) -> None:
        dt = datetime(2026, 6, 8, 9, 30, tzinfo=CHINA_TZ)
        self.assertEqual(bar_session_minute(dt), 0.0)

    def test_morning_close(self) -> None:
        dt = datetime(2026, 6, 8, 11, 30, tzinfo=CHINA_TZ)
        self.assertEqual(bar_session_minute(dt), float(MORNING_SESSION_MINUTES))

    def test_afternoon_open_collapses_lunch(self) -> None:
        dt = datetime(2026, 6, 8, 13, 0, tzinfo=CHINA_TZ)
        self.assertEqual(bar_session_minute(dt), float(MORNING_SESSION_MINUTES))

    def test_afternoon_close(self) -> None:
        dt = datetime(2026, 6, 8, 15, 0, tzinfo=CHINA_TZ)
        self.assertEqual(bar_session_minute(dt), float(INTRADAY_SESSION_MINUTES))


class IntradayChartDataTests(unittest.TestCase):
    def test_avg_price_near_close(self) -> None:
        bars = [
            _bar(9, 30, close=1272.0, volume=600, amount=76_320_000.0),
            _bar(9, 31, close=1272.85, volume=501, amount=63_769_785.0),
        ]
        avg_prices = calc_intraday_avg_prices(bars)
        self.assertAlmostEqual(avg_prices[0], 1272.0, places=2)
        self.assertAlmostEqual(avg_prices[1], 1272.43, places=1)
        self.assertLess(abs(avg_prices[1] - bars[1].close_price), 5.0)

    def test_session_x_skips_lunch_gap(self) -> None:
        bars = [
            _bar(11, 30, close=1270.0, volume=10, amount=1_270_000.0),
            _bar(13, 0, close=1271.0, volume=10, amount=1_271_000.0),
        ]
        xs = session_x_values(bars)
        self.assertEqual(xs[0], float(MORNING_SESSION_MINUTES))
        self.assertEqual(xs[1], float(MORNING_SESSION_MINUTES))

    def test_price_y_range_uses_prev_close(self) -> None:
        y_min, y_max = price_y_range([1260.0, 1270.0], prev_close=1250.0)
        self.assertLess(y_min, 1250.0)
        self.assertGreater(y_max, 1270.0)

    def test_nearest_bar_index(self) -> None:
        xs = [0.0, 1.0, 2.0, 5.0]
        self.assertEqual(nearest_bar_index(xs, 1.1), 1)
        self.assertEqual(nearest_bar_index(xs, 4.0), 3)
        self.assertEqual(nearest_bar_index(xs, -1.0), 0)

    def test_format_intraday_summary(self) -> None:
        bar = _bar(10, 15, close=1270.0, volume=10, amount=1_270_000.0)
        text = format_intraday_summary(bar, avg_price=1268.5, prev_close=1260.0)
        self.assertIn("10:15", text)
        self.assertIn("1270.00", text)
        self.assertIn("1268.50", text)
        self.assertIn("+10.00", text)
        self.assertIn("10手", text)

    def test_pct_change_and_tick(self) -> None:
        self.assertAlmostEqual(pct_change(1260.0, 1200.0), 5.0)
        self.assertEqual(format_pct_tick(1260.0, 1200.0), "+5.00%")

    def test_build_price_segments_splits_at_prev_close(self) -> None:
        xs = [0.0, 1.0, 2.0, 3.0]
        prices = [101.0, 99.0, 100.0, 102.0]
        segments = build_price_segments(xs, prices, prev_close=100.0)
        self.assertEqual(len(segments), 3)
        self.assertTrue(segments[0][2])
        self.assertFalse(segments[1][2])
        self.assertTrue(segments[2][2])
        self.assertAlmostEqual(segments[0][0][-1], 0.5, places=3)
        self.assertAlmostEqual(segments[0][1][-1], 100.0, places=3)

    def test_build_price_segments_single_side(self) -> None:
        xs = [0.0, 1.0, 2.0]
        prices = [101.0, 102.0, 103.0]
        segments = build_price_segments(xs, prices, prev_close=100.0)
        self.assertEqual(len(segments), 1)
        self.assertTrue(segments[0][2])

    def test_volume_helpers(self) -> None:
        bar_up = _bar(9, 45, close=1271.0, volume=120, amount=1.0)
        bar_up.open_price = 1270.0
        bar_down = _bar(9, 46, close=1269.0, volume=80, amount=1.0)
        bar_down.open_price = 1270.0
        self.assertEqual(volume_bar_color(bar_up), RISE_RGB)
        self.assertEqual(volume_bar_color(bar_down), FALL_RGB)
        self.assertEqual(format_volume_lots(15000), "1.50万手")
        vol_min, vol_max = volume_y_range([10, 100, 50])
        self.assertEqual(vol_min, 0.0)
        self.assertAlmostEqual(vol_max, 112.0)


if __name__ == "__main__":
    unittest.main()
