"""雷达行行情补全与盘中刷新。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vnpy_ashare.domain.core.numbers import float_or_none
from vnpy_ashare.domain.market.quote_row import QuoteRowLike, QuoteRowsLike
from vnpy_ashare.domain.radar.card import RadarCardData, RadarRow
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.radar.radar_leader import board_quality_score
from vnpy_ashare.quotes.radar.radar_quotes import merge_row_quotes, quotes_for_vt_symbols
from vnpy_ashare.quotes.radar.radar_relative_strength import (
    RelativeStrengthContext,
    build_relative_strength_context,
    enrich_radar_row_relative_strength,
)
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

__all__ = [
    "apply_board_quality",
    "collect_radar_quote_vt_symbols",
    "enrich_radar_row",
    "enrich_radar_rows",
    "refresh_radar_card_quotes_from_map",
    "refresh_radar_rows_live_quotes",
]


def apply_board_quality(row: RadarRow, payload: QuoteRowLike | Mapping[str, Any]) -> RadarRow:
    """为涨停/连板行写入 board_quality（已有则跳过）。"""
    if row.board_quality is not None:
        return row
    score = board_quality_score(payload)
    if score is None:
        return row
    return row.model_copy(update={"board_quality": score})


def enrich_radar_row(
    row: RadarRow,
    quote: dict[str, Any],
    *,
    snapshot_rows: QuoteRowsLike | None = None,
    rs_context: RelativeStrengthContext | None = None,
    preserve_sub: bool = False,
) -> RadarRow:
    """用全市场行情补全 RadarRow 的现价、涨幅与相对强度副标题。"""

    merged = merge_row_quotes(quote, prefer_row=is_ashare_trading_session())
    price = float_or_none(merged.get("last_price") or merged.get("close"))
    if price is None:
        price = row.price
    change_pct = float_or_none(
        merged.get("change_pct") or quote.get("change_pct") or quote.get("pct_chg"),
    )
    if change_pct is None:
        change_pct = row.change_pct
    updated = row
    if price != row.price or change_pct != row.change_pct:
        updated = row.model_copy(update={"price": price, "change_pct": change_pct})
    updated = apply_board_quality(updated, merged)
    return enrich_radar_row_relative_strength(
        updated,
        merged,
        snapshot_rows=snapshot_rows,
        rs_context=rs_context,
        preserve_sub=preserve_sub,
    )


def refresh_radar_rows_live_quotes(rows: tuple[RadarRow, ...]) -> tuple[RadarRow, ...]:
    """仅刷新现价/涨幅，不重算相对强度或预加载 ScreeningContext。"""
    if not rows:
        return rows
    quotes = quotes_for_vt_symbols([row.vt_symbol for row in rows])
    return _refresh_rows_from_quote_map(rows, quotes)


def _refresh_rows_from_quote_map(
    rows: tuple[RadarRow, ...],
    quotes: dict[str, dict[str, Any]],
) -> tuple[RadarRow, ...]:
    refreshed: list[RadarRow] = []
    for row in rows:
        quote = quotes.get(row.vt_symbol, {})
        price = float_or_none(quote.get("last_price") or quote.get("close"))
        change_pct = float_or_none(quote.get("change_pct"))
        updates: dict[str, Any] = {}
        if price is not None and price != row.price:
            updates["price"] = price
        if change_pct is not None and change_pct != row.change_pct:
            updates["change_pct"] = change_pct
        refreshed.append(row.model_copy(update=updates) if updates else row)
    return tuple(refreshed)


def refresh_radar_card_quotes_from_map(
    data: RadarCardData,
    quotes: dict[str, dict[str, Any]],
) -> RadarCardData:
    """用已批量拉取的行情映射刷新单卡行（避免重复 Redis / 快照查询）。"""
    if not data.rows:
        return data
    refreshed = _refresh_rows_from_quote_map(data.rows, quotes)
    if refreshed is data.rows:
        return data
    return data.model_copy(update={"rows": refreshed})


def collect_radar_quote_vt_symbols(cards: list[RadarCardData]) -> list[str]:
    """收集多卡待刷新行情的 vt_symbol（去重，跳过统计行）。"""
    symbols: list[str] = []
    seen: set[str] = set()
    for data in cards:
        for row in data.rows:
            vt_symbol = row.vt_symbol
            if not vt_symbol or vt_symbol.startswith("__stat__:") or vt_symbol in seen:
                continue
            seen.add(vt_symbol)
            symbols.append(vt_symbol)
    return symbols


def enrich_radar_rows(
    rows: tuple[RadarRow, ...],
    *,
    preserve_sub: bool = False,
) -> tuple[RadarRow, ...]:
    """批量补全雷达行行情字段。"""
    if not rows:
        return rows
    quotes = quotes_for_vt_symbols([row.vt_symbol for row in rows])
    snapshot_rows: QuoteRowsLike | None = None
    try:
        snapshot_rows = load_screening_quote_snapshot().rows
    except MarketQuotesLoadError:
        snapshot_rows = None
    rs_context = build_relative_strength_context(snapshot_rows)
    return tuple(
        enrich_radar_row(
            row,
            quotes.get(row.vt_symbol, {"vt_symbol": row.vt_symbol}),
            snapshot_rows=snapshot_rows,
            rs_context=rs_context,
            preserve_sub=preserve_sub,
        )
        for row in rows
    )
