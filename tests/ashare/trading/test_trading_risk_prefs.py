"""交易参数 QSettings 读写。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.config.preferences.trading_risk import (
    TradingRiskPrefs,
    load_trading_risk_prefs,
    save_trading_risk_prefs,
)


class TradingRiskPrefsTest(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        mock_settings = MagicMock()
        store: dict[str, object] = {}

        def set_value(key: str, value: object) -> None:
            store[key] = value

        def value(key: str, default=None):
            return store.get(key, default)

        mock_settings.setValue.side_effect = set_value
        mock_settings.value.side_effect = value
        mock_settings.sync = MagicMock()

        with patch("vnpy_ashare.config.preferences.trading_risk.get_settings", return_value=mock_settings):
            save_trading_risk_prefs(
                TradingRiskPrefs(
                    total_capital=200_000.0,
                    stop_loss_pct=0.04,
                    caution_float_pct=-6.0,
                    realized_pnl_today=-300.0,
                )
            )
            loaded = load_trading_risk_prefs()
        self.assertEqual(loaded.total_capital, 200_000.0)
        self.assertAlmostEqual(loaded.stop_loss_pct, 0.04)
        self.assertAlmostEqual(loaded.caution_float_pct, -6.0)
        self.assertAlmostEqual(loaded.realized_pnl_today, -300.0)


if __name__ == "__main__":
    unittest.main()
