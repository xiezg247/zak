"""极致短线 onboarding 偏好测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.config.preferences.onboarding import (
    load_ultra_short_onboarding_done,
    save_ultra_short_onboarding_done,
)
from vnpy_ashare.ui.quotes.onboarding.ultra_short import should_offer_ultra_short_onboarding


class UltraShortOnboardingPrefsTest(unittest.TestCase):
    def setUp(self) -> None:
        save_ultra_short_onboarding_done(False)

    def tearDown(self) -> None:
        save_ultra_short_onboarding_done(True)

    def test_should_offer_when_not_done_and_default_profile(self) -> None:
        with patch(
            "vnpy_ashare.ui.quotes.onboarding.ultra_short.load_strategy_profile_id",
            return_value="medium_watch",
        ):
            self.assertTrue(should_offer_ultra_short_onboarding())

    def test_should_not_offer_when_done(self) -> None:
        save_ultra_short_onboarding_done(True)
        self.assertFalse(should_offer_ultra_short_onboarding())

    def test_load_save_roundtrip(self) -> None:
        self.assertFalse(load_ultra_short_onboarding_done())
        save_ultra_short_onboarding_done(True)
        self.assertTrue(load_ultra_short_onboarding_done())


if __name__ == "__main__":
    unittest.main()
