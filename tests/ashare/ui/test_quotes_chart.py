"""K 线图中文游标测试。"""

from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta

from vnpy.chart.manager import BarManager
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from vnpy_ashare.ui.components.chart_style import FALL_RGB, RISE_RGB
from vnpy_ashare.ui.quotes.chart.daily import (
    DAILY_BAR_COUNT,
    MINUTE_BAR_COUNT,
    WATCHLIST_DAILY_DEFAULT_BAR_COUNT,
    AshareCandleItem,
    AshareChartWidget,
    AshareVolumeItem,
    ChineseCandleItem,
    ChineseVolumeItem,
    create_watchlist_chart,
    prepare_chart_bars,
)
from vnpy_ashare.ui.quotes.chart.ma_line_item import calc_sma, ma_line_item_class
from vnpy_ashare.ui.quotes.chart.minute_bars import MinuteBarDiff, compute_minute_bar_change


def _sample_bar() -> BarData:
    return BarData(
        symbol="600519",
        exchange=Exchange.SSE,
        datetime=datetime(2024, 6, 5, 15, 0, 0),
        interval=Interval.DAILY,
        open_price=1700.0,
        high_price=1710.0,
        low_price=1690.0,
        close_price=1705.0,
        volume=12345,
        gateway_name="TEST",
    )


def _minute_bars(count: int, *, start_minute: int = 0) -> list[BarData]:
    bars: list[BarData] = []
    for index in range(count):
        bars.append(
            BarData(
                symbol="002230",
                exchange=Exchange.SZSE,
                datetime=datetime(2026, 6, 5, 9, 30 + start_minute + index, 0),
                interval=Interval.MINUTE,
                open_price=40.0 + index,
                high_price=41.0 + index,
                low_price=39.0 + index,
                close_price=40.5 + index,
                volume=1000 + index,
                gateway_name="TEST",
            )
        )
    return bars


def _daily_bars(count: int, *, start_day: int = 1) -> list[BarData]:
    bars: list[BarData] = []
    anchor = datetime(2024, 1, start_day, 15, 0, 0)
    for index in range(count):
        bars.append(
            BarData(
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=anchor + timedelta(days=index),
                interval=Interval.DAILY,
                open_price=1700.0 + index,
                high_price=1710.0 + index,
                low_price=1690.0 + index,
                close_price=1705.0 + index,
                volume=12345 + index,
                gateway_name="TEST",
            )
        )
    return bars


class PrepareChartBarsTests(unittest.TestCase):
    def test_dedupe_same_datetime(self) -> None:
        bars = _minute_bars(3)
        bars.append(
            BarData(
                symbol=bars[0].symbol,
                exchange=bars[0].exchange,
                datetime=bars[1].datetime,
                interval=bars[1].interval,
                open_price=99.0,
                high_price=99.0,
                low_price=99.0,
                close_price=99.0,
                volume=1,
                gateway_name="TEST",
            )
        )
        prepared = prepare_chart_bars(bars)
        self.assertEqual(len(prepared), 3)
        self.assertEqual(prepared[1].close_price, 99.0)


class TestAshareChartWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from vnpy.trader.ui import QtWidgets

        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _create_chart(self) -> AshareChartWidget:
        chart = AshareChartWidget(bar_count=MINUTE_BAR_COUNT)
        chart.add_plot("candle", hide_x_axis=True, minimum_height=200)
        chart.add_plot("volume", maximum_height=120, minimum_height=60)
        chart.add_item(AshareCandleItem, "candle", "candle")
        chart.add_item(AshareVolumeItem, "volume", "volume")
        chart.add_cursor()
        return chart

    def test_replace_history_resets_viewport(self) -> None:
        chart = self._create_chart()
        chart.replace_history(_minute_bars(3))
        chart._bar_count = 200
        chart._right_ix = 99

        chart.replace_history(_minute_bars(2, start_minute=10))

        self.assertEqual(chart._manager.get_count(), 2)
        self.assertEqual(chart._bar_count, MINUTE_BAR_COUNT)
        self.assertEqual(chart._right_ix, 2)
        self.assertEqual(chart._cursor._x, 1)
        last_bar = chart._manager.get_bar(1)
        assert last_bar is not None
        self.assertEqual(chart._cursor._y, last_bar.close_price)

    def test_replace_history_does_not_merge_old_period(self) -> None:
        chart = self._create_chart()
        chart.replace_history(_minute_bars(4))
        chart.replace_history(_minute_bars(2, start_minute=20))

        self.assertEqual(chart._manager.get_count(), 2)
        first = chart._manager.get_bar(0)
        assert first is not None
        self.assertEqual(first.datetime.minute, 50)

    def test_replace_history_fewer_bars_resyncs_view(self) -> None:
        chart = self._create_chart()
        chart.replace_history(_daily_bars(80))
        chart._first_plot.getViewBox().setRange(xRange=(60, 80), padding=0)

        chart.replace_history(_daily_bars(10, start_day=5))

        self.assertEqual(chart._manager.get_count(), 10)
        self.assertEqual(chart._right_ix, 10)
        min_x, max_x = chart._first_plot.getViewBox().viewRange()[0]
        self.assertLessEqual(max_x, 11)
        self.assertGreaterEqual(min_x, -chart._bar_count)

    def test_update_history_delegates_to_replace_not_merge(self) -> None:
        chart = self._create_chart()
        chart.replace_history(_minute_bars(4))
        chart.update_history(_minute_bars(2, start_minute=20))

        self.assertEqual(chart._manager.get_count(), 2)
        first = chart._manager.get_bar(0)
        assert first is not None
        self.assertEqual(first.datetime.minute, 50)

    def test_set_viewport_bar_count_without_reload(self) -> None:
        chart = self._create_chart()
        chart.replace_history(_daily_bars(80))

        chart.set_viewport_bar_count(10)

        self.assertEqual(chart._default_bar_count, 10)
        self.assertEqual(chart._bar_count, 10)
        self.assertEqual(chart._right_ix, 80)
        min_x, max_x = chart._first_plot.getViewBox().viewRange()[0]
        self.assertAlmostEqual(max_x, 80.0, places=3)
        self.assertAlmostEqual(min_x, 70.0, places=3)

    def test_short_viewport_y_range_includes_candle_highs(self) -> None:
        chart = create_watchlist_chart(minute=False)
        chart.replace_history(_daily_bars(80))
        chart.set_viewport_bar_count(5)

        min_ix, max_ix = chart._visible_ix_range()
        candle = chart._items["candle"]
        candle_min, candle_max = candle.get_y_range(min_ix, max_ix)
        _, plot_y_max = chart._first_plot.viewRange()[1]
        self.assertGreaterEqual(plot_y_max, candle_max)

    def test_create_watchlist_daily_chart_defaults_to_60_bars(self) -> None:
        chart = create_watchlist_chart(minute=False)
        self.assertEqual(chart._default_bar_count, WATCHLIST_DAILY_DEFAULT_BAR_COUNT)
        self.assertEqual(WATCHLIST_DAILY_DEFAULT_BAR_COUNT, 60)

    def test_create_watchlist_daily_chart_all_preset_matches_daily_count(self) -> None:
        chart = create_watchlist_chart(minute=False)
        chart.replace_history(_daily_bars(DAILY_BAR_COUNT))
        chart.set_viewport_bar_count(DAILY_BAR_COUNT)
        self.assertEqual(chart._bar_count, DAILY_BAR_COUNT)
        min_x, max_x = chart._first_plot.getViewBox().viewRange()[0]
        self.assertAlmostEqual(max_x, float(DAILY_BAR_COUNT), places=3)


class TestChineseChartItems(unittest.TestCase):
    def setUp(self) -> None:
        manager = BarManager()
        manager.update_history([_sample_bar()])
        self.candle = ChineseCandleItem(manager)
        self.volume = ChineseVolumeItem(manager)

    def test_candle_info_text(self) -> None:
        text = self.candle.get_info_text(0)
        self.assertIn("日期", text)
        self.assertIn("开盘", text)
        self.assertIn("最高", text)
        self.assertIn("最低", text)
        self.assertIn("收盘", text)
        self.assertNotIn("Date", text)
        self.assertNotIn("Open", text)

    def test_volume_info_text(self) -> None:
        text = self.volume.get_info_text(0)
        self.assertIn("成交量", text)
        self.assertNotIn("Volume", text)

    def test_calc_sma(self) -> None:
        bars = []
        for index in range(5):
            bar = _sample_bar()
            bar.close_price = 100 + index
            bars.append(bar)
        values = calc_sma(bars, 3)
        self.assertTrue(math.isnan(values[0]))
        self.assertTrue(math.isnan(values[1]))
        self.assertAlmostEqual(values[2], 101.0)
        self.assertAlmostEqual(values[-1], 103.0)

    def test_ma_line_bounding_rect(self) -> None:
        manager = BarManager()
        manager.update_history([_sample_bar()])
        ma_class = ma_line_item_class(5, "#ffffff", "MA5")
        ma_item = ma_class(manager)
        ma_item.update_history([_sample_bar()])
        rect = ma_item.boundingRect()
        self.assertIsNotNone(rect)
        self.assertGreater(rect.width(), 0)

    def test_ashare_candle_colors(self) -> None:
        manager = BarManager()
        manager.update_history([_sample_bar()])
        candle = AshareCandleItem(manager)
        self.assertEqual(candle._up_brush.color().getRgb()[:3], RISE_RGB)
        self.assertEqual(candle._down_brush.color().getRgb()[:3], FALL_RGB)


class MinuteBarDiffTests(unittest.TestCase):
    def test_noop_when_unchanged(self) -> None:
        bars = _minute_bars(3)
        change = compute_minute_bar_change(bars, bars)
        self.assertEqual(change.diff, MinuteBarDiff.NOOP)

    def test_tail_patch_updates_last_bar(self) -> None:
        bars = _minute_bars(3)
        updated = list(bars)
        updated[-1] = BarData(
            symbol=updated[-1].symbol,
            exchange=updated[-1].exchange,
            datetime=updated[-1].datetime,
            interval=updated[-1].interval,
            open_price=updated[-1].open_price,
            high_price=updated[-1].high_price,
            low_price=updated[-1].low_price,
            close_price=updated[-1].close_price + 1.0,
            volume=updated[-1].volume,
            gateway_name=updated[-1].gateway_name,
        )
        change = compute_minute_bar_change(bars, updated)
        self.assertEqual(change.diff, MinuteBarDiff.TAIL_PATCH)
        self.assertEqual(change.patch_from, 2)

    def test_apply_bars_tail_patch_preserves_viewport(self) -> None:
        from vnpy.trader.ui import QtWidgets

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        chart = create_watchlist_chart(minute=True)
        chart.show()
        QtWidgets.QApplication.processEvents()

        bars = _minute_bars(30)
        chart.replace_history(bars)
        chart._bar_count = 20
        chart._right_ix = 30
        chart._update_x_range()

        updated = list(bars)
        last = updated[-1]
        updated[-1] = BarData(
            symbol=last.symbol,
            exchange=last.exchange,
            datetime=last.datetime,
            interval=last.interval,
            open_price=last.open_price,
            high_price=last.high_price + 2.0,
            low_price=last.low_price,
            close_price=last.close_price + 1.0,
            volume=last.volume + 10,
            gateway_name=last.gateway_name,
        )
        change = compute_minute_bar_change(bars, updated)
        chart.apply_bars(change)

        self.assertEqual(chart._manager.get_count(), 30)
        self.assertEqual(chart._right_ix, 30)
        self.assertEqual(chart._manager.get_bar(29).close_price, updated[-1].close_price)
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
