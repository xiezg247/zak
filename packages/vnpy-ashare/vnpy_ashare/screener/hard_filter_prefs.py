"""选股硬过滤用户偏好（QSettings）；环境变量仍可覆盖。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.constants.recipe import DEFAULT_MIN_AMOUNT_YUAN, DEFAULT_MIN_TOTAL_MV_WAN
from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.config.preferences._settings import get_settings

_SETTINGS = get_settings()
_KEY_EXCLUDE_ST = "screener/hard_filter/exclude_st"
_KEY_EXCLUDE_SUSPENDED = "screener/hard_filter/exclude_suspended"
_KEY_MIN_AMOUNT_WAN = "screener/hard_filter/min_amount_wan"
_KEY_MIN_TOTAL_MV_YI = "screener/hard_filter/min_total_mv_yi"
_KEY_EXCLUDE_NEW_LISTING = "screener/hard_filter/exclude_new_listing"
_KEY_MIN_LISTING_DAYS = "screener/hard_filter/min_listing_days"
_KEY_EXCLUDE_LIMIT_BOARD = "screener/hard_filter/exclude_limit_board"
_KEY_ALLOWED_INDUSTRIES = "screener/hard_filter/allowed_industries"
_KEY_ALLOWED_MARKET_BOARDS = "screener/hard_filter/allowed_market_boards"

MARKET_BOARD_FILTER_OPTIONS = ("沪深主板", "创业板", "科创板", "北交所")

PRESET_CONSERVATIVE = "conservative"
PRESET_BALANCED = "balanced"
PRESET_AGGRESSIVE = "aggressive"


class HardFilterPrefs(FrozenModel):
    exclude_st: bool = Field(description="是否排除 ST 股")
    exclude_suspended: bool = Field(description="是否排除停牌股")
    min_amount_wan: float = Field(description="最低成交额（万元）")
    min_total_mv_yi: float = Field(description="最低总市值（亿元）")
    exclude_new_listing: bool = Field(description="是否排除新股")
    min_listing_days: int = Field(description="最低上市天数")
    exclude_limit_board: bool = Field(description="是否排除连板涨停股")
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
    defaults = default_hard_filter_prefs()
    exclude_st = _SETTINGS.value(_KEY_EXCLUDE_ST)
    if exclude_st is None:
        exclude = defaults.exclude_st
    else:
        exclude = str(exclude_st).strip().lower() not in ("0", "false", "no")

    exclude_suspended = _SETTINGS.value(_KEY_EXCLUDE_SUSPENDED)
    if exclude_suspended is None:
        exclude_suspend = defaults.exclude_suspended
    else:
        exclude_suspend = str(exclude_suspended).strip().lower() not in ("0", "false", "no")

    exclude_new = _SETTINGS.value(_KEY_EXCLUDE_NEW_LISTING)
    if exclude_new is None:
        exclude_new_listing = defaults.exclude_new_listing
    else:
        exclude_new_listing = str(exclude_new).strip().lower() not in ("0", "false", "no")

    exclude_limit = _SETTINGS.value(_KEY_EXCLUDE_LIMIT_BOARD)
    if exclude_limit is None:
        exclude_limit_board = defaults.exclude_limit_board
    else:
        exclude_limit_board = str(exclude_limit).strip().lower() not in ("0", "false", "no")

    amount_wan = _read_float(_SETTINGS.value(_KEY_MIN_AMOUNT_WAN), defaults.min_amount_wan)
    mv_yi = _read_float(_SETTINGS.value(_KEY_MIN_TOTAL_MV_YI), defaults.min_total_mv_yi)
    listing_days = _read_int(_SETTINGS.value(_KEY_MIN_LISTING_DAYS), defaults.min_listing_days)
    allowed_raw = _SETTINGS.value(_KEY_ALLOWED_INDUSTRIES)
    allowed_industries = normalize_allowed_industries_text(str(allowed_raw or defaults.allowed_industries))
    boards_raw = _SETTINGS.value(_KEY_ALLOWED_MARKET_BOARDS)
    allowed_market_boards = normalize_allowed_market_boards_text(str(boards_raw or defaults.allowed_market_boards))
    return HardFilterPrefs(
        exclude_st=exclude,
        exclude_suspended=exclude_suspend,
        min_amount_wan=max(0.0, amount_wan),
        min_total_mv_yi=max(0.0, mv_yi),
        exclude_new_listing=exclude_new_listing,
        min_listing_days=max(0, listing_days),
        exclude_limit_board=exclude_limit_board,
        allowed_industries=allowed_industries,
        allowed_market_boards=allowed_market_boards,
    )


def save_hard_filter_prefs(prefs: HardFilterPrefs) -> None:
    _SETTINGS.setValue(_KEY_EXCLUDE_ST, prefs.exclude_st)
    _SETTINGS.setValue(_KEY_EXCLUDE_SUSPENDED, prefs.exclude_suspended)
    _SETTINGS.setValue(_KEY_MIN_AMOUNT_WAN, prefs.min_amount_wan)
    _SETTINGS.setValue(_KEY_MIN_TOTAL_MV_YI, prefs.min_total_mv_yi)
    _SETTINGS.setValue(_KEY_EXCLUDE_NEW_LISTING, prefs.exclude_new_listing)
    _SETTINGS.setValue(_KEY_MIN_LISTING_DAYS, prefs.min_listing_days)
    _SETTINGS.setValue(_KEY_EXCLUDE_LIMIT_BOARD, prefs.exclude_limit_board)
    _SETTINGS.setValue(_KEY_ALLOWED_INDUSTRIES, prefs.allowed_industries)
    _SETTINGS.setValue(_KEY_ALLOWED_MARKET_BOARDS, prefs.allowed_market_boards)


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


def _read_float(raw, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _read_int(raw, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default
