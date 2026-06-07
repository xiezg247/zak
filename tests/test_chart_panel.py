"""自选图表 Tab 提示文案测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.models import StockItem
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.chart_panel import (
    DAILY_MISSING_HINT,
    DAILY_TAB_INDEX,
    LIVE_INTRADAY_HINT,
    LIVE_MINUTE_HINT,
    LOCAL_MINUTE_HINT,
    MINUTE_TAB_INDEX,
    chart_tab_hint,
    is_same_minute_request,
    retain_thread_until_finished,
    should_apply_minute_bars,
)
from vnpy_ashare.ui.worker import MinuteBarsWorker


class ChartTabHintTests(unittest.TestCase):
    def test_intraday_hint(self) -> None:
        self.assertEqual(chart_tab_hint(0), LIVE_INTRADAY_HINT)

    def test_minute_hint(self) -> None:
        text = chart_tab_hint(MINUTE_TAB_INDEX)
        self.assertEqual(text, LIVE_MINUTE_HINT)
        self.assertIn("TickFlow", text)

    def test_minute_local_hint(self) -> None:
        text = chart_tab_hint(
            MINUTE_TAB_INDEX,
            minute_from_local=True,
            minute_start="2026-01-01",
            minute_end="2026-06-01 15:00",
            minute_count=1200,
        )
        self.assertEqual(text, LOCAL_MINUTE_HINT.format(
            start="2026-01-01",
            end="2026-06-01 15:00",
            count=1200,
        ))

    def test_daily_missing_hint(self) -> None:
        self.assertEqual(
            chart_tab_hint(DAILY_TAB_INDEX, daily_missing=True),
            DAILY_MISSING_HINT,
        )

    def test_daily_with_data_no_hint(self) -> None:
        self.assertIsNone(chart_tab_hint(DAILY_TAB_INDEX, daily_missing=False))


class SameMinuteRequestTests(unittest.TestCase):
    def test_same_symbol_and_period(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        worker = MinuteBarsWorker(item, period="1m")
        self.assertTrue(
            is_same_minute_request(
                worker,
                period="1m",
                target_key=("600519", Exchange.SSE),
            )
        )

    def test_different_symbol_same_period(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        worker = MinuteBarsWorker(item, period="1m")
        self.assertFalse(
            is_same_minute_request(
                worker,
                period="1m",
                target_key=("000001", Exchange.SZSE),
            )
        )


class RetainThreadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_retain_keeps_reference_until_finished(self) -> None:
        class SlowWorker(QtCore.QThread):
            finished = QtCore.Signal()

            def run(self) -> None:
                self.msleep(50)
                self.finished.emit()

        retired: list[QtCore.QThread] = []
        worker = SlowWorker()
        retain_thread_until_finished(retired, worker)
        self.assertIn(worker, retired)
        worker.start()
        self.assertTrue(worker.wait(2000))
        deadline = QtCore.QDeadlineTimer(2000)
        while worker in retired and not deadline.hasExpired():
            QtWidgets.QApplication.processEvents()
        self.assertNotIn(worker, retired)


class MinuteBarsApplyTests(unittest.TestCase):
    def test_apply_when_period_and_tab_match(self) -> None:
        self.assertTrue(
            should_apply_minute_bars(
                target_period="1m",
                current_period="1m",
                tab_index=MINUTE_TAB_INDEX,
                loaded_period="1m",
            )
        )

    def test_reject_wrong_tab(self) -> None:
        self.assertFalse(
            should_apply_minute_bars(
                target_period="1m",
                current_period="1m",
                tab_index=DAILY_TAB_INDEX,
                loaded_period="1m",
            )
        )

    def test_reject_mismatched_loaded_period(self) -> None:
        self.assertFalse(
            should_apply_minute_bars(
                target_period="1m",
                current_period="1m",
                tab_index=MINUTE_TAB_INDEX,
                loaded_period="5m",
            )
        )


if __name__ == "__main__":
    unittest.main()
