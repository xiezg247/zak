"""将选股结果收窄至极致短线主池（P1-2）。"""

from __future__ import annotations

from collections.abc import Sequence

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.hard_filter_prefs import PRESET_AGGRESSIVE, hard_filter_preset
from vnpy_ashare.screener.hard_filters import (
    is_row_suspended,
    is_st_stock,
    limit_board_threshold_pct,
    row_amount_yuan,
    _suspended_keys_for_screening,
)

__all__ = ["filter_ultra_short_main_pool", "is_ultra_short_popularity_row"]

_MAIN_BOARD_MAX_MV_WAN = 2_000_000.0  # 200 亿
_CM20_MAX_MV_WAN = 1_500_000.0  # 150 亿
_MAIN_BOARD_MIN_MV_WAN = 300_000.0  # 30 亿
_CM20_MIN_MV_WAN = 200_000.0  # 20 亿
_MIN_CHANGE_PCT = 7.0
_MIN_LEADER_SCORE = 40.0


def _row_mapping(row: ScreenerResultRow) -> dict:
    return row.to_dict()


def _is_cm20(vt_symbol: str) -> bool:
    symbol = vt_symbol.split(".")[0]
    return symbol.startswith(("300", "688"))


def _passes_ultra_short_mv_band(row: dict) -> bool:
    vt_symbol = str(row.get("vt_symbol") or "")
    total_mv = float(row.get("total_mv") or row.get("circ_mv") or 0)
    if total_mv <= 0:
        return True
    if _is_cm20(vt_symbol):
        return _CM20_MIN_MV_WAN <= total_mv <= _CM20_MAX_MV_WAN
    return _MAIN_BOARD_MIN_MV_WAN <= total_mv <= _MAIN_BOARD_MAX_MV_WAN


def is_ultra_short_popularity_row(row: ScreenerResultRow | dict) -> bool:
    payload = row if isinstance(row, dict) else _row_mapping(row)
    limit_times = float(payload.get("limit_times") or 0)
    if limit_times >= 1:
        return True
    change = float(payload.get("change_pct") or payload.get("pct_chg") or 0)
    if change >= _MIN_CHANGE_PCT:
        return True
    leader_score = payload.get("leader_score")
    if leader_score is not None and float(leader_score) >= _MIN_LEADER_SCORE:
        return True
    if str(payload.get("source") or "") == "radar_leader":
        return True
    threshold = limit_board_threshold_pct(payload)
    if change >= threshold - 0.5:
        return True
    return False


def _passes_aggressive_hard_filter(row: ScreenerResultRow) -> bool:
    prefs = hard_filter_preset(PRESET_AGGRESSIVE)
    mapping = _row_mapping(row)
    name = str(mapping.get("name") or "")
    if prefs.exclude_st and is_st_stock(name):
        return False
    if prefs.exclude_suspended:
        if is_row_suspended(mapping, _suspended_keys_for_screening()):
            return False
    amount = float(mapping.get("amount") or 0) or row_amount_yuan(mapping)
    if amount > 0 and amount < prefs.min_amount_yuan:
        return False
    total_mv = float(mapping.get("total_mv") or mapping.get("circ_mv") or 0)
    if total_mv > 0 and total_mv < prefs.min_total_mv_wan:
        return False
    return _passes_ultra_short_mv_band(mapping)


def filter_ultra_short_main_pool(rows: Sequence[ScreenerResultRow]) -> list[ScreenerResultRow]:
    """硬过滤（激进）+ 人气/连板/龙头评分，收窄至短线主池。"""
    result: list[ScreenerResultRow] = []
    for row in rows:
        if not _passes_aggressive_hard_filter(row):
            continue
        if not is_ultra_short_popularity_row(row):
            continue
        result.append(row)
    return result
