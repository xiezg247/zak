"""Polars 硬过滤（与 ``hard_filters.apply_recipe_filters`` 语义对齐）。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import polars as pl

from vnpy_ashare.domain.symbols.stock import vt_symbol_to_ts_code
from vnpy_ashare.screener.engine.frame import restore_rows, rows_with_index
from vnpy_ashare.screener.hard_filters import ONE_WORD_AMPLITUDE_MAX_PCT
from vnpy_ashare.screener import hard_filters as hf


def _symbol_expr() -> pl.Expr:
    vt = pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("")
    from_vt = vt.str.split(".").list.first()
    return pl.coalesce(pl.col("symbol").cast(pl.Utf8, strict=False), from_vt).fill_null("")


def _change_pct_expr() -> pl.Expr:
    return pl.coalesce(
        pl.col("change_pct").cast(pl.Float64, strict=False),
        pl.col("pct_chg").cast(pl.Float64, strict=False),
    ).fill_null(0.0)


def _limit_threshold_expr(market_col: pl.Expr, symbol_col: pl.Expr) -> pl.Expr:
    market = market_col.fill_null("")
    is_growth = market.is_in(["创业板", "科创板"]) | symbol_col.str.starts_with("300") | symbol_col.str.starts_with("688")
    return pl.when(is_growth).then(pl.lit(19.5)).otherwise(pl.lit(9.8))


def _board_match_expr(symbol_col: pl.Expr, board: str) -> pl.Expr:
    if board == "沪深主板":
        prefixes = ("600", "601", "603", "000", "001", "002", "003")
        return pl.any_horizontal([symbol_col.str.starts_with(prefix) for prefix in prefixes])
    if board == "创业板":
        return symbol_col.str.starts_with("300")
    if board == "科创板":
        return symbol_col.str.starts_with("688")
    if board == "北交所":
        return pl.any_horizontal([symbol_col.str.starts_with("8"), symbol_col.str.starts_with("4")])
    return pl.lit(True)


def _market_board_mask(symbol_col: pl.Expr, allowed: frozenset[str]) -> pl.Expr:
    if not allowed:
        return pl.lit(False)
    return pl.any_horizontal([_board_match_expr(symbol_col, board) for board in allowed])


def _st_mask(name_col: pl.Expr, mapped_name_col: pl.Expr) -> pl.Expr:
    primary = name_col.fill_null("").str.to_uppercase()
    secondary = mapped_name_col.fill_null("").str.to_uppercase()
    return primary.str.contains("ST") | secondary.str.contains("ST")


def _liquidity_mask(min_amount: float, min_mv: float) -> pl.Expr:
    amount = pl.col("amount").cast(pl.Float64, strict=False)
    total_mv = pl.coalesce(
        pl.col("total_mv").cast(pl.Float64, strict=False),
        pl.col("circ_mv").cast(pl.Float64, strict=False),
    )
    amount_ok = (amount > 0) & ((pl.lit(min_amount) <= 0) | (amount >= min_amount))
    mv_ok = (total_mv > 0) & ((pl.lit(min_mv) <= 0) | (total_mv >= min_mv))
    return (
        pl.when(amount > 0)
        .then(amount_ok)
        .when(total_mv > 0)
        .then(mv_ok)
        .otherwise(pl.lit(min_amount <= 0))
    )


def _join_map(df: pl.DataFrame, key_col: str, mapping: dict[str, str], value_col: str) -> pl.DataFrame:
    if not mapping:
        return df.with_columns(pl.lit(None).cast(pl.Utf8).alias(value_col))
    map_df = pl.DataFrame({"_map_key": list(mapping.keys()), value_col: list(mapping.values())})
    return df.join(map_df, left_on=key_col, right_on="_map_key", how="left")


def _ensure_columns(df: pl.DataFrame, names: Sequence[str]) -> pl.DataFrame:
    missing = [name for name in names if name not in df.columns]
    if not missing:
        return df
    return df.with_columns(pl.lit(None).alias(name) for name in missing)


_OPTIONAL_COLS = (
    "symbol",
    "exchange",
    "name",
    "industry",
    "list_date",
    "market",
    "pct_chg",
    "change_pct",
    "high_price",
    "high",
    "low_price",
    "low",
    "prev_close",
    "pre_close",
    "open_price",
    "open",
    "amount",
    "total_mv",
    "circ_mv",
)


def apply_recipe_filters_polars(rows: Sequence[Any]) -> list[Any]:
    """Polars 向量化硬过滤；返回与输入同类型的行列表。"""
    if not rows:
        return []

    payloads, _ = rows_with_index(rows)
    df = pl.DataFrame(payloads, infer_schema_length=max(len(payloads), 1))
    df = _ensure_columns(df, _OPTIONAL_COLS)

    symbol_col = _symbol_expr()
    change_col = _change_pct_expr()
    df = df.with_columns(
        symbol_col.alias("_symbol"),
        change_col.alias("_change_pct"),
        pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").alias("_vt_symbol"),
    )

    mask = pl.lit(True)

    board_filter = hf.resolve_market_board_filter()
    if board_filter.active:
        mask = mask & _market_board_mask(pl.col("_symbol"), board_filter.boards)

    allowed_industries = hf.recipe_allowed_industries()
    if allowed_industries:
        industry_map = hf._industry_map_for_screening()
        df = df.with_columns(
            pl.col("_vt_symbol")
            .map_elements(lambda vt: vt_symbol_to_ts_code(str(vt or "")) or "", return_dtype=pl.Utf8)
            .alias("_ts_code")
        )
        df = _join_map(df, "_ts_code", industry_map, "_mapped_industry")
        industry_col = pl.coalesce(pl.col("industry").cast(pl.Utf8, strict=False), pl.col("_mapped_industry"))
        mask = mask & industry_col.is_in(list(allowed_industries))

    if hf.recipe_exclude_suspended_enabled():
        suspended_keys = hf._suspended_keys_for_screening()
        if suspended_keys:
            sym = pl.coalesce(pl.col("symbol").cast(pl.Utf8, strict=False), pl.col("_symbol"))
            ex = pl.coalesce(
                pl.col("exchange").cast(pl.Utf8, strict=False),
                pl.col("_vt_symbol").str.split(".").list.last(),
            )
            suspend_key = sym + pl.lit("|") + ex
            suspended_labels = [f"{a}|{b}" for a, b in suspended_keys]
            has_suspend_key = (sym.str.len_chars() > 0) & (ex.str.len_chars() > 0)
            mask = mask & (~has_suspend_key | ~suspend_key.is_in(suspended_labels))

    if hf.recipe_exclude_st_enabled():
        name_map = hf._screening_vt_name_map()
        df = _join_map(df, "_vt_symbol", name_map, "_mapped_name")
        mask = mask & ~_st_mask(pl.col("name").cast(pl.Utf8, strict=False), pl.col("_mapped_name"))

    if hf.recipe_exclude_new_listing_enabled():
        min_days = hf.recipe_min_listing_days()
        if min_days > 0:
            list_date_map = hf._list_date_map_for_screening()
            df = _join_map(df, "_vt_symbol", list_date_map, "_mapped_list_date")
            list_date_raw = pl.coalesce(
                pl.col("list_date").cast(pl.Utf8, strict=False),
                pl.col("_mapped_list_date").cast(pl.Utf8, strict=False),
            ).fill_null("")
            listed = list_date_raw.str.slice(0, 8).str.strptime(pl.Date, "%Y%m%d", strict=False)
            today = date.today()
            days = (pl.lit(today) - listed).dt.total_days()
            mask = mask & (
                (list_date_raw.str.len_chars() < 8) | days.is_null() | (days >= min_days)
            )

    market_board_map: dict[str, str] | None = None
    if hf.recipe_exclude_limit_board_enabled() or hf.recipe_exclude_one_word_enabled():
        market_board_map = hf._market_board_map_for_screening()
        df = _join_map(df, "_vt_symbol", market_board_map, "_mapped_market")
        market_col = pl.coalesce(pl.col("market").cast(pl.Utf8, strict=False), pl.col("_mapped_market"))
        df = df.with_columns(market_col.alias("_market"))
        threshold = _limit_threshold_expr(pl.col("_market"), pl.col("_symbol"))

        if hf.recipe_exclude_limit_board_enabled():
            mask = mask & (pl.col("_change_pct") < threshold) & (pl.col("_change_pct") > -threshold)

        if hf.recipe_exclude_one_word_enabled():
            high = pl.coalesce(
                pl.col("high_price").cast(pl.Float64, strict=False),
                pl.col("high").cast(pl.Float64, strict=False),
            )
            low = pl.coalesce(
                pl.col("low_price").cast(pl.Float64, strict=False),
                pl.col("low").cast(pl.Float64, strict=False),
            )
            prev_close = pl.coalesce(
                pl.col("prev_close").cast(pl.Float64, strict=False),
                pl.col("pre_close").cast(pl.Float64, strict=False),
            )
            open_price = pl.coalesce(
                pl.col("open_price").cast(pl.Float64, strict=False),
                pl.col("open").cast(pl.Float64, strict=False),
            )
            amplitude_prev = pl.when((high > 0) & (low > 0) & (prev_close > 0)).then((high - low) / prev_close * 100.0)
            amplitude_open = pl.when((open_price > 0) & (high > 0) & (low > 0)).then((high - low) / open_price * 100.0)
            amplitude = pl.coalesce(amplitude_prev, amplitude_open).fill_null(999.0)
            is_one_word = (pl.col("_change_pct") >= threshold - 0.3) & (amplitude >= 0) & (amplitude < ONE_WORD_AMPLITUDE_MAX_PCT)
            mask = mask & ~is_one_word

    min_amount = hf.recipe_min_amount_yuan()
    min_mv = hf.recipe_min_total_mv_wan()
    mask = mask & _liquidity_mask(min_amount, min_mv)

    filtered = df.filter(mask).to_dicts()
    return restore_rows(rows, filtered)
