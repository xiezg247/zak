"""选股硬过滤（ST、停牌、流动性 / 小市值）。

配方、策略 preset、形态选股共用；QSettings 用户偏好与环境变量 ``RECIPE_*`` 均可生效（环境变量优先）。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import TypeVar

from vnpy_ashare.config.constants.recipe import (
    DEFAULT_MIN_AMOUNT_YUAN,
    DEFAULT_MIN_LISTING_DAYS,
    DEFAULT_MIN_TOTAL_MV_WAN,
    ENV_ALLOWED_INDUSTRIES,
    ENV_ALLOWED_MARKET_BOARDS,
    ENV_EXCLUDE_LIMIT_BOARD,
    ENV_EXCLUDE_NEW_LISTING,
    ENV_EXCLUDE_ONE_WORD,
    ENV_EXCLUDE_ST,
    ENV_EXCLUDE_SUSPENDED,
    ENV_MIN_AMOUNT_YUAN,
    ENV_MIN_LISTING_DAYS,
    ENV_MIN_TOTAL_MV_WAN,
)
from vnpy_ashare.config.trading_universe import MarketBoardFilter, effective_market_board_filter
from vnpy_ashare.domain.core.env import (
    env_or_prefs_bool,
    env_or_prefs_nonneg_float,
    env_or_prefs_nonneg_int,
    env_or_prefs_str,
)
from vnpy_ashare.domain.market.board import matches_board
from vnpy_ashare.domain.screener.result_row import ScreeningFilterRow
from vnpy_ashare.domain.symbols.stock import ts_code_to_vt_symbol, vt_symbol_to_ts_code
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.integrations.tushare.factors import (
    fetch_stock_basic_snapshot,
    fetch_stock_industry_map,
    fetch_stock_market_board_map,
)
from vnpy_ashare.screener.hard_filter_prefs import (
    load_hard_filter_prefs,
    parse_allowed_industries,
    parse_allowed_market_boards,
)
from vnpy_ashare.storage.repositories.symbol_suspend import ensure_suspend_keys_for_screening
from vnpy_ashare.storage.repositories.symbols import build_symbol_name_map

T_ScreeningRow = TypeVar("T_ScreeningRow", bound=ScreeningFilterRow)

_suspend_keys_cache: tuple[date, frozenset[tuple[str, str]]] | None = None
_list_date_map_cache: tuple[date, dict[str, str]] | None = None
_market_board_map_cache: tuple[date, dict[str, str]] | None = None
_industry_map_cache: tuple[date, dict[str, str]] | None = None


def recipe_min_amount_yuan() -> float:
    return env_or_prefs_nonneg_float(
        ENV_MIN_AMOUNT_YUAN,
        default=DEFAULT_MIN_AMOUNT_YUAN,
        prefs=lambda: load_hard_filter_prefs().min_amount_yuan,
    )


def recipe_exclude_st_enabled() -> bool:
    return env_or_prefs_bool(ENV_EXCLUDE_ST, prefs=lambda: load_hard_filter_prefs().exclude_st)


def recipe_exclude_suspended_enabled() -> bool:
    return env_or_prefs_bool(ENV_EXCLUDE_SUSPENDED, prefs=lambda: load_hard_filter_prefs().exclude_suspended)


def recipe_min_total_mv_wan() -> float:
    return env_or_prefs_nonneg_float(
        ENV_MIN_TOTAL_MV_WAN,
        default=DEFAULT_MIN_TOTAL_MV_WAN,
        prefs=lambda: load_hard_filter_prefs().min_total_mv_wan,
    )


def recipe_exclude_new_listing_enabled() -> bool:
    return env_or_prefs_bool(ENV_EXCLUDE_NEW_LISTING, prefs=lambda: load_hard_filter_prefs().exclude_new_listing)


def recipe_min_listing_days() -> int:
    return env_or_prefs_nonneg_int(
        ENV_MIN_LISTING_DAYS,
        default=DEFAULT_MIN_LISTING_DAYS,
        prefs=lambda: load_hard_filter_prefs().min_listing_days,
    )


def recipe_exclude_limit_board_enabled() -> bool:
    return env_or_prefs_bool(ENV_EXCLUDE_LIMIT_BOARD, prefs=lambda: load_hard_filter_prefs().exclude_limit_board)


def recipe_exclude_one_word_enabled() -> bool:
    return env_or_prefs_bool(ENV_EXCLUDE_ONE_WORD, prefs=lambda: load_hard_filter_prefs().exclude_one_word)


def recipe_allowed_industries() -> frozenset[str]:
    raw = env_or_prefs_str(ENV_ALLOWED_INDUSTRIES, prefs=lambda: load_hard_filter_prefs().allowed_industries)
    return parse_allowed_industries(raw)


def recipe_preference_market_boards() -> frozenset[str]:
    """选股硬过滤中的板块白名单（不含账户交易上限）。"""
    raw = env_or_prefs_str(ENV_ALLOWED_MARKET_BOARDS, prefs=lambda: load_hard_filter_prefs().allowed_market_boards)
    return parse_allowed_market_boards(raw)


def resolve_market_board_filter(
    *,
    recipe_boards: frozenset[str] | None = None,
    override_boards: frozenset[str] | None = None,
) -> MarketBoardFilter:
    """解析市场板块过滤；``active`` 为 False 表示不限制板块。"""
    if override_boards is not None:
        return MarketBoardFilter(active=True, boards=override_boards)
    recipe = recipe_preference_market_boards() if recipe_boards is None else recipe_boards
    return effective_market_board_filter(recipe_boards=recipe)


def recipe_allowed_market_boards() -> frozenset[str]:
    """有效板块白名单：账户交易上限 ∩ 选股偏好（二者均未设时为空集）。"""
    return resolve_market_board_filter().boards


def is_st_stock(name: str) -> bool:
    text = (name or "").strip().upper()
    return "ST" in text


def _screening_vt_name_map() -> dict[str, str]:
    """vt_symbol → 名称；用于 row.name 缺失或与 universe 不一致时的 ST 判定。"""
    mapping: dict[str, str] = {}
    for (symbol, exchange), name in build_symbol_name_map().items():
        if name:
            mapping[f"{symbol}.{exchange.value}"] = name
    return mapping


def _names_for_st_check(row: ScreeningFilterRow, name_map: dict[str, str] | None) -> list[str]:
    candidates: list[str] = []
    for candidate in (
        str(row.get("name") or "").strip(),
        str((name_map or {}).get(str(row.get("vt_symbol") or "").strip()) or "").strip(),
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def row_amount_yuan(row: ScreeningFilterRow) -> float:
    amount = row.get("amount")
    if amount not in (None, ""):
        return float(amount or 0)
    # Tushare daily_basic 无 amount 时用 close * volume 粗估（volume 为手时需 ×100，此处仅作兜底）
    close = float(row.get("close") or row.get("last_price") or 0)
    volume = float(row.get("volume") or 0)
    if close > 0 and volume > 0:
        return close * volume * 100
    return 0.0


def row_symbol_exchange(row: ScreeningFilterRow) -> tuple[str, str] | None:
    symbol = str(row.get("symbol") or "").strip()
    exchange = str(row.get("exchange") or "").strip()
    if symbol and exchange:
        return symbol, exchange
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if "." in vt_symbol:
        sym, ex = vt_symbol.rsplit(".", 1)
        if sym and ex:
            return sym, ex
    return None


def clear_suspend_screening_cache() -> None:
    global _suspend_keys_cache, _list_date_map_cache, _market_board_map_cache, _industry_map_cache
    _suspend_keys_cache = None
    _list_date_map_cache = None
    _market_board_map_cache = None
    _industry_map_cache = None


def _suspended_keys_for_screening() -> frozenset[tuple[str, str]]:
    global _suspend_keys_cache

    day = last_trading_day()
    if _suspend_keys_cache is not None and _suspend_keys_cache[0] == day:
        return _suspend_keys_cache[1]
    keys = ensure_suspend_keys_for_screening(trade_date=day)
    _suspend_keys_cache = (day, keys)
    return keys


def is_row_suspended(row: ScreeningFilterRow, suspended_keys: frozenset[tuple[str, str]]) -> bool:
    key = row_symbol_exchange(row)
    return key is not None and key in suspended_keys


def _list_date_map_for_screening() -> dict[str, str]:
    global _list_date_map_cache

    day = last_trading_day()
    if _list_date_map_cache is not None and _list_date_map_cache[0] == day:
        return _list_date_map_cache[1]

    rows, _ = fetch_stock_basic_snapshot()
    mapping: dict[str, str] = {}
    for item in rows:
        ts_code = str(item.get("ts_code") or "").strip()
        list_date = str(item.get("list_date") or "").strip()
        if not ts_code or not list_date:
            continue
        vt_symbol = _ts_code_to_vt_symbol(ts_code)
        if vt_symbol:
            mapping[vt_symbol] = list_date
    _list_date_map_cache = (day, mapping)
    return mapping


def _market_board_map_for_screening() -> dict[str, str]:
    global _market_board_map_cache

    day = last_trading_day()
    if _market_board_map_cache is not None and _market_board_map_cache[0] == day:
        return _market_board_map_cache[1]

    board_map = fetch_stock_market_board_map()
    mapping = {_ts_code_to_vt_symbol(ts_code): market for ts_code, market in board_map.items() if _ts_code_to_vt_symbol(ts_code)}
    _market_board_map_cache = (day, mapping)
    return mapping


def _industry_map_for_screening() -> dict[str, str]:
    global _industry_map_cache

    day = last_trading_day()
    if _industry_map_cache is not None and _industry_map_cache[0] == day:
        return _industry_map_cache[1]

    try:
        mapping = fetch_stock_industry_map()
    except Exception:
        mapping = {}
    _industry_map_cache = (day, mapping)
    return mapping


def row_symbol(row: ScreeningFilterRow) -> str:
    symbol = str(row.get("symbol") or "").strip()
    if symbol:
        return symbol
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if "." in vt_symbol:
        return vt_symbol.split(".", 1)[0]
    return vt_symbol


def passes_market_board_filter(row: ScreeningFilterRow, allowed: frozenset[str]) -> bool:
    if not allowed:
        return False

    symbol = row_symbol(row)
    if not symbol:
        return False
    return any(matches_board(symbol, board) for board in allowed)


def passes_recipe_market_board_vt_symbol(vt_symbol: str) -> bool:
    """标的是否落在有效板块白名单内；未配置板块过滤时恒为 True。"""
    board_filter = resolve_market_board_filter()
    if not board_filter.active:
        return True
    from vnpy_ashare.domain.symbols.stock import parse_stock_symbol

    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return False
    return passes_market_board_filter(
        {"symbol": item.symbol, "vt_symbol": vt_symbol},
        board_filter.boards,
    )


def filter_vt_symbols_by_recipe_market_board(vt_symbols: Sequence[str]) -> list[str]:
    """按配方/账户板块白名单过滤 vt_symbol 列表。"""
    board_filter = resolve_market_board_filter()
    if not board_filter.active:
        return list(vt_symbols)
    return [vt for vt in vt_symbols if passes_recipe_market_board_vt_symbol(vt)]


def row_industry(row: ScreeningFilterRow, industry_map: dict[str, str] | None = None) -> str:
    industry = str(row.get("industry") or "").strip()
    if industry:
        return industry
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return ""
    ts_code = vt_symbol_to_ts_code(vt_symbol)
    if not ts_code:
        return ""
    mapping = industry_map if industry_map is not None else _industry_map_for_screening()
    return str(mapping.get(ts_code) or "").strip()


def passes_industry_filter(row: ScreeningFilterRow, allowed: frozenset[str], industry_map: dict[str, str] | None = None) -> bool:
    if not allowed:
        return True
    industry = row_industry(row, industry_map)
    if not industry:
        return False
    return industry in allowed


def _ts_code_to_vt_symbol(ts_code: str) -> str:
    return ts_code_to_vt_symbol(ts_code) or ""


def is_new_listing(row: ScreeningFilterRow, list_date_map: dict[str, str] | None = None) -> bool:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return False
    list_date_raw = str(row.get("list_date") or "").strip()
    if not list_date_raw:
        mapping = list_date_map if list_date_map is not None else _list_date_map_for_screening()
        list_date_raw = str(mapping.get(vt_symbol) or "").strip()
    if not list_date_raw or len(list_date_raw) < 8:
        return False
    try:
        listed = datetime.strptime(list_date_raw[:8], "%Y%m%d").date()
    except ValueError:
        return False
    min_days = recipe_min_listing_days()
    if min_days <= 0:
        return False
    return (date.today() - listed).days < min_days


def limit_board_threshold_pct(row: ScreeningFilterRow, market_board_map: dict[str, str] | None = None) -> float:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    market = str(row.get("market") or "").strip()
    if not market and vt_symbol:
        mapping = market_board_map if market_board_map is not None else _market_board_map_for_screening()
        market = str(mapping.get(vt_symbol) or "").strip()
    if market in ("创业板", "科创板"):
        return 19.5
    symbol = str(row.get("symbol") or vt_symbol.split(".")[0])
    if symbol.startswith(("300", "688")):
        return 19.5
    return 9.8


def is_at_limit_board(row: ScreeningFilterRow, market_board_map: dict[str, str] | None = None) -> bool:
    change = float(row.get("change_pct") or row.get("pct_chg") or 0)
    threshold = limit_board_threshold_pct(row, market_board_map=market_board_map)
    return change >= threshold or change <= -threshold


ONE_WORD_AMPLITUDE_MAX_PCT = 0.5


def is_one_word_limit_board(
    row: ScreeningFilterRow,
    *,
    market_board_map: dict[str, str] | None = None,
    max_amplitude_pct: float = ONE_WORD_AMPLITUDE_MAX_PCT,
) -> bool:
    """涨停且日内振幅极小（近似一字板）。"""
    threshold = limit_board_threshold_pct(row, market_board_map=market_board_map)
    change = float(row.get("change_pct") or row.get("pct_chg") or 0)
    if change < threshold - 0.3:
        return False
    high = float(row.get("high_price") or row.get("high") or 0)
    low = float(row.get("low_price") or row.get("low") or 0)
    prev_close = float(row.get("prev_close") or row.get("pre_close") or 0)
    if high > 0 and low > 0 and prev_close > 0:
        amplitude = (high - low) / prev_close * 100
        return 0 <= amplitude < max_amplitude_pct
    open_price = float(row.get("open_price") or row.get("open") or 0)
    if open_price > 0 and high > 0 and low > 0:
        amplitude = (high - low) / open_price * 100
        return 0 <= amplitude < max_amplitude_pct
    return False


def passes_liquidity_filter(row: ScreeningFilterRow) -> bool:
    """成交额或总市值（小资金）达标；无相关字段时不排除。"""
    min_amount = recipe_min_amount_yuan()
    min_mv = recipe_min_total_mv_wan()

    amount_raw = row.get("amount")
    if amount_raw not in (None, ""):
        amount_val = float(amount_raw or 0)
        if amount_val > 0:
            if min_amount <= 0:
                return True
            return amount_val >= min_amount

    total_mv = float(row.get("total_mv") or row.get("circ_mv") or 0)
    if total_mv > 0:
        if min_mv <= 0:
            return True
        return total_mv >= min_mv

    estimated = row_amount_yuan(row)
    if estimated > 0 and min_amount > 0:
        return estimated >= min_amount

    return True


def passes_screening_hard_filter(
    row: ScreeningFilterRow,
    *,
    suspended_keys: frozenset[tuple[str, str]] | None = None,
    name_map: dict[str, str] | None = None,
    list_date_map: dict[str, str] | None = None,
    market_board_map: dict[str, str] | None = None,
    industry_map: dict[str, str] | None = None,
    allowed_industries: frozenset[str] | None = None,
    allowed_market_boards: frozenset[str] | None = None,
) -> bool:
    if allowed_market_boards is not None:
        board_filter = MarketBoardFilter(active=True, boards=allowed_market_boards)
    else:
        board_filter = resolve_market_board_filter()
    if board_filter.active and not passes_market_board_filter(row, board_filter.boards):
        return False
    allowed = allowed_industries if allowed_industries is not None else recipe_allowed_industries()
    if allowed and not passes_industry_filter(row, allowed, industry_map=industry_map):
        return False
    if recipe_exclude_suspended_enabled():
        keys = suspended_keys if suspended_keys is not None else _suspended_keys_for_screening()
        if is_row_suspended(row, keys):
            return False
    if recipe_exclude_st_enabled():
        for name in _names_for_st_check(row, name_map):
            if is_st_stock(name):
                return False
    if recipe_exclude_new_listing_enabled() and is_new_listing(row, list_date_map=list_date_map):
        return False
    if recipe_exclude_limit_board_enabled() and is_at_limit_board(row, market_board_map=market_board_map):
        return False
    if recipe_exclude_one_word_enabled() and is_one_word_limit_board(row, market_board_map=market_board_map):
        return False
    return passes_liquidity_filter(row)


def apply_recipe_filters(rows: Sequence[T_ScreeningRow]) -> list[T_ScreeningRow]:
    """排除 ST、停牌与流动性 / 小市值不达标的标的。"""
    from vnpy_ashare.screener.engine.config import polars_available, polars_engine_enabled

    if polars_engine_enabled() and polars_available():
        from vnpy_ashare.screener.engine.hard_filter import apply_recipe_filters_polars

        return apply_recipe_filters_polars(rows)

    allowed_industries = recipe_allowed_industries()
    suspended_keys = _suspended_keys_for_screening() if recipe_exclude_suspended_enabled() else frozenset()
    name_map = _screening_vt_name_map() if recipe_exclude_st_enabled() else None
    list_date_map = _list_date_map_for_screening() if recipe_exclude_new_listing_enabled() else None
    market_board_map = _market_board_map_for_screening() if recipe_exclude_limit_board_enabled() or recipe_exclude_one_word_enabled() else None
    industry_map = _industry_map_for_screening() if allowed_industries else None
    return [
        row
        for row in rows
        if passes_screening_hard_filter(
            row,
            suspended_keys=suspended_keys,
            name_map=name_map,
            list_date_map=list_date_map,
            market_board_map=market_board_map,
            industry_map=industry_map,
            allowed_industries=allowed_industries,
        )
    ]
