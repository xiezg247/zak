"""板块资金策略展望偏好测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
    load_sector_flow_outlook_strategy_class,
    save_sector_flow_outlook_strategy_class,
)


class SectorFlowOutlookStrategyPrefsTests(unittest.TestCase):
    def test_save_and_load_sector_flow_strategy(self) -> None:
        with mock.patch("vnpy_ashare.quotes.radar.outlook_strategy_prefs.get_settings") as get_settings:
            store: dict[str, str] = {}

            class _Settings:
                def value(self, key: str, default: str = "") -> str:
                    return store.get(key, default)

                def setValue(self, key: str, value: str) -> None:
                    store[key] = value

            get_settings.return_value = _Settings()
            with mock.patch(
                "vnpy_ashare.quotes.radar.outlook_strategy_prefs.OUTLOOK_STRATEGY_WHITELIST",
                ("AshareDoubleMaStrategy",),
            ):
                with mock.patch(
                    "vnpy_ashare.quotes.radar.outlook_strategy_prefs._WHITELIST_SET",
                    frozenset({"AshareDoubleMaStrategy"}),
                ):
                    save_sector_flow_outlook_strategy_class("AshareDoubleMaStrategy")
                    self.assertEqual(load_sector_flow_outlook_strategy_class(), "AshareDoubleMaStrategy")

    def test_fallback_to_radar_when_unset(self) -> None:
        with mock.patch("vnpy_ashare.quotes.radar.outlook_strategy_prefs.get_settings") as get_settings:

            class _Settings:
                def value(self, _key: str, default: str = "") -> str:
                    return default

            get_settings.return_value = _Settings()
            with mock.patch(
                "vnpy_ashare.quotes.radar.outlook_strategy_prefs.load_outlook_strategy_class",
                return_value="RadarStrategy",
            ):
                self.assertEqual(load_sector_flow_outlook_strategy_class(), "RadarStrategy")


if __name__ == "__main__":
    unittest.main()
