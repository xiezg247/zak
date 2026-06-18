"""新用户极致短线 onboarding QSettings。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings

ULTRA_SHORT_ONBOARDING_KEY = "trading/onboarding/ultra_short_v1_done"


def load_ultra_short_onboarding_done() -> bool:
    return coerce_settings_bool(get_settings().value(ULTRA_SHORT_ONBOARDING_KEY), default=False)


def save_ultra_short_onboarding_done(done: bool = True) -> None:
    settings = get_settings()
    settings.setValue(ULTRA_SHORT_ONBOARDING_KEY, done)
    settings.sync()
