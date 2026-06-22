"""策略 Profile 首次引导测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.config.preferences.onboarding import (
    load_profile_onboarding_done,
    save_profile_onboarding_done,
)
from vnpy_ashare.ui.quotes.onboarding.ultra_short import (
    layout_preset_for_profile,
    should_offer_profile_onboarding,
)


class ProfileOnboardingPrefsTest(unittest.TestCase):
    def setUp(self) -> None:
        save_profile_onboarding_done(False)

    def tearDown(self) -> None:
        save_profile_onboarding_done(True)

    def test_should_offer_when_not_done(self) -> None:
        self.assertTrue(should_offer_profile_onboarding())

    def test_should_not_offer_when_done(self) -> None:
        save_profile_onboarding_done(True)
        self.assertFalse(should_offer_profile_onboarding())

    def test_load_save_roundtrip(self) -> None:
        self.assertFalse(load_profile_onboarding_done())
        save_profile_onboarding_done(True)
        self.assertTrue(load_profile_onboarding_done())

    def test_layout_preset_for_profile(self) -> None:
        self.assertEqual(layout_preset_for_profile("ultra_short"), "intraday")
        self.assertEqual(layout_preset_for_profile("short_swing"), "intraday")
        self.assertEqual(layout_preset_for_profile("medium_watch"), "review")
        self.assertEqual(layout_preset_for_profile("trend"), "review")


if __name__ == "__main__":
    unittest.main()
