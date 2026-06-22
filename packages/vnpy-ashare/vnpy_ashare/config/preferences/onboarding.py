"""新用户策略 Profile 首次引导 QSettings。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings

PROFILE_ONBOARDING_KEY = "trading/onboarding/profile_v1_done"
# 兼容旧键：曾用 ultra_short_v1_done
_LEGACY_ONBOARDING_KEY = "trading/onboarding/ultra_short_v1_done"


def load_profile_onboarding_done() -> bool:
    settings = get_settings()
    if coerce_settings_bool(settings.value(PROFILE_ONBOARDING_KEY), default=False):
        return True
    return coerce_settings_bool(settings.value(_LEGACY_ONBOARDING_KEY), default=False)


def save_profile_onboarding_done(done: bool = True) -> None:
    settings = get_settings()
    settings.setValue(PROFILE_ONBOARDING_KEY, done)
    settings.remove(_LEGACY_ONBOARDING_KEY)
    settings.sync()


def load_ultra_short_onboarding_done() -> bool:
    return load_profile_onboarding_done()


def save_ultra_short_onboarding_done(done: bool = True) -> None:
    save_profile_onboarding_done(done)
