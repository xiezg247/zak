"""新用户策略 Profile 首次引导 QSettings。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings

PROFILE_ONBOARDING_KEY = "trading/onboarding/profile_v1_done"


def load_profile_onboarding_done() -> bool:
    settings = get_settings()
    return coerce_settings_bool(settings.value(PROFILE_ONBOARDING_KEY), default=False)


def save_profile_onboarding_done(done: bool = True) -> None:
    settings = get_settings()
    settings.setValue(PROFILE_ONBOARDING_KEY, done)
    settings.sync()
