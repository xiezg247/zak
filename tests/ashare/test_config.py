"""A 股回测默认参数与配置检测。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vnpy_ashare.config.runtime import ASHARE_BACKTEST_DEFAULTS, EFFECTIVE_RATE, LOT_SIZE, PRICE_TICK, _looks_like_futures_config, ensure_runtime_config, format_decimal_field, write_backtest_defaults


class AshareBacktestConfigTest(unittest.TestCase):
    def test_defaults_are_ashare(self) -> None:
        self.assertEqual(ASHARE_BACKTEST_DEFAULTS["vt_symbol"], "600519.SSE")
        self.assertEqual(ASHARE_BACKTEST_DEFAULTS["size"], 1)
        self.assertEqual(ASHARE_BACKTEST_DEFAULTS["pricetick"], PRICE_TICK)
        self.assertEqual(ASHARE_BACKTEST_DEFAULTS["rate"], EFFECTIVE_RATE)
        self.assertEqual(ASHARE_BACKTEST_DEFAULTS["slippage"], PRICE_TICK)
        self.assertEqual(EFFECTIVE_RATE, 0.00045)

    def test_effective_rate_json_no_float_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cta_backtester_setting.json"
            write_backtest_defaults(path)
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("999999", raw)
            data = json.loads(raw)
            self.assertEqual(data["rate"], 0.00045)

    def test_format_decimal_field(self) -> None:
        noisy = (0.0002 + 0.0002 + 0.0005) / 2
        self.assertEqual(format_decimal_field(noisy, places=6), "0.00045")
        self.assertEqual(format_decimal_field(0.01, places=4), "0.01")

    def test_futures_config_detection(self) -> None:
        self.assertTrue(_looks_like_futures_config({"vt_symbol": "IF88.CFFEX", "size": 1}))
        self.assertTrue(_looks_like_futures_config({"vt_symbol": "600519.SSE", "size": 300}))
        self.assertFalse(_looks_like_futures_config({"vt_symbol": "600519.SSE", "size": 1}))

    def test_write_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cta_backtester_setting.json"
            write_backtest_defaults(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["class_name"], "AshareDoubleMaStrategy")
            self.assertEqual(data["size"], 1)

    def test_ensure_replaces_futures_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cta_backtester_setting.json"
            path.write_text(
                json.dumps({"vt_symbol": "IF88.CFFEX", "size": 300}),
                encoding="utf-8",
            )
            import vnpy_ashare.config.runtime as runtime

            original = runtime.BACKTESTER_SETTING_FILE
            try:
                runtime.BACKTESTER_SETTING_FILE = path
                changed = ensure_runtime_config(force=False)
                self.assertTrue(changed)
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(data["vt_symbol"], "600519.SSE")
            finally:
                runtime.BACKTESTER_SETTING_FILE = original


class BacktestChartDataTest(unittest.TestCase):
    def test_balance_series_needs_to_numpy_for_pyqtgraph(self) -> None:
        import pandas as pd

        dates = pd.date_range("2026-01-05", periods=3)
        df = pd.DataFrame({"balance": [1_000_000.0, 1_000_000.0, 999_000.0]}, index=dates)
        with self.assertRaises(KeyError):
            _ = df["balance"][0]
        values = df["balance"].to_numpy()
        self.assertEqual(values[0], 1_000_000.0)
        self.assertEqual(values[2], 999_000.0)


class AshareTemplateTest(unittest.TestCase):
    def test_normalize_volume(self) -> None:
        from vnpy_ashare.config.runtime import normalize_volume

        self.assertEqual(normalize_volume(50), LOT_SIZE)
        self.assertEqual(normalize_volume(150), 100)
        self.assertEqual(normalize_volume(200), 200)
