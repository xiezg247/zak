"""选股硬过滤用户偏好（user_preferences）；环境变量仍可覆盖。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.constants.recipe import DEFAULT_MIN_AMOUNT_YUAN, DEFAULT_MIN_TOTAL_MV_WAN
from vnpy_ashare.config.preferences._user_pref import load_model_pref, save_model_pref
from vnpy_common.domain.base import FrozenModel

_PREF_NAMESPACE = "screener"
_PREF_KEY = "hard_filter"

MARKET_BOARD_FILTER_OPTIONS = ("沪深主板", "创业板", "科创板", "北交所")

PRESET_CONSERVATIVE = "conservative"
PRESET_BALANCED = "balanced"
PRESET_AGGRESSIVE = "aggressive"

STRATEGY_PROFILE_HARD_FILTER_PRESET: dict[str, str] = {
    "ultra_short": PRESET_AGGRESSIVE,
    "short_swing": PRESET_BALANCED,
    "medium_watch": PRESET_BALANCED,
    "trend": PRESET_CONSERVATIVE,
}


class HardFilterPrefs(FrozenModel):
    exclude_st: bool = Field(description="是否排除 ST 股")
    exclude_suspended: bool = Field(description="是否排除停牌股")
    min_amount_wan: float = Field(description="最低成交额（万元）")
    min_total_mv_yi: float = Field(description="最低总市值（亿元）")
    exclude_new_listing: bool = Field(description="是否排除新股")
    min_listing_days: int = Field(description="最低上市天数")
    exclude_limit_board: bool = Field(description="是否排除连板涨停股")
    exclude_one_word: bool = Field(default=False, description="是否排除一字涨停（振幅极小）")
    allowed_industries: str = Field(default="", description="允许的行业（逗号分隔）")
    allowed_market_boards: str = Field(default="", description="允许的板块（逗号分隔）")

    @property
    def min_amount_yuan(self) -> float:
        return max(0.0, self.min_amount_wan) * 10_000.0

    @property
    def min_total_mv_wan(self) -> float:
        return max(0.0, self.min_total_mv_yi) * 10_000.0


def default_hard_filter_prefs() -> HardFilterPrefs:
    return HardFilterPrefs(
        exclude_st=True,
        exclude_suspended=True,
        min_amount_wan=DEFAULT_MIN_AMOUNT_YUAN / 10_000.0,
        min_total_mv_yi=DEFAULT_MIN_TOTAL_MV_WAN / 10_000.0,
        exclude_new_listing=False,
        min_listing_days=60,
        exclude_limit_board=False,
        allowed_industries="",
        allowed_market_boards="",
    )


def hard_filter_preset(preset_id: str) -> HardFilterPrefs:
    defaults = default_hard_filter_prefs()
    if preset_id == PRESET_CONSERVATIVE:
        return HardFilterPrefs(
            exclude_st=True,
            exclude_suspended=True,
            min_amount_wan=5000.0,
            min_total_mv_yi=100.0,
            exclude_new_listing=True,
            min_listing_days=60,
            exclude_limit_board=True,
            allowed_industries="",
            allowed_market_boards="",
        )
    if preset_id == PRESET_AGGRESSIVE:
        return HardFilterPrefs(
            exclude_st=True,
            exclude_suspended=True,
            min_amount_wan=5000.0,
            min_total_mv_yi=30.0,
            exclude_new_listing=False,
            min_listing_days=60,
            exclude_limit_board=False,
            allowed_industries="",
            allowed_market_boards="",
        )
    return defaults


def load_hard_filter_prefs() -> HardFilterPrefs:
    return load_model_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        HardFilterPrefs,
        load_default=default_hard_filter_prefs,
    )


def save_hard_filter_prefs(prefs: HardFilterPrefs) -> None:
    save_model_pref(_PREF_NAMESPACE, _PREF_KEY, prefs)


def normalize_allowed_industries_text(raw: str) -> str:
    """逗号分隔的行业名；去空白、统一中文逗号。"""
    text = (raw or "").replace("，", ",").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return ",".join(parts)


def parse_allowed_industries(raw: str) -> frozenset[str]:
    normalized = normalize_allowed_industries_text(raw)
    if not normalized:
        return frozenset()
    return frozenset(normalized.split(","))


def normalize_allowed_market_boards_text(raw: str) -> str:
    text = (raw or "").replace("，", ",").strip()
    if not text:
        return ""
    valid = set(MARKET_BOARD_FILTER_OPTIONS)
    parts = [part.strip() for part in text.split(",") if part.strip() in valid]
    return ",".join(parts)


def parse_allowed_market_boards(raw: str) -> frozenset[str]:
    normalized = normalize_allowed_market_boards_text(raw)
    if not normalized:
        return frozenset()
    return frozenset(normalized.split(","))


def apply_hard_filter_preset(preset_id: str) -> HardFilterPrefs:
    prefs = hard_filter_preset(preset_id)
    save_hard_filter_prefs(prefs)
    return prefs


def hard_filter_preset_for_strategy_profile(profile_id: str) -> str:
    return STRATEGY_PROFILE_HARD_FILTER_PRESET.get(profile_id, PRESET_BALANCED)


def sync_hard_filter_for_strategy_profile(profile_id: str) -> HardFilterPrefs:
    """策略 Profile 切换时同步硬过滤模板（保守 / 均衡 / 激进）。"""
    return apply_hard_filter_preset(hard_filter_preset_for_strategy_profile(profile_id))
