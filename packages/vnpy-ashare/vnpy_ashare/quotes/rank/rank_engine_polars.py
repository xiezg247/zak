"""Polars 行情榜过滤与排序。"""

from __future__ import annotations

import polars as pl

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.rank.rank_catalog import RankDefinition
from vnpy_ashare.quotes.rank.rank_engine import quote_matches_rank, quote_rank_value


def finalize_rank_catalog_polars(
    tf_symbols: list[str],
    quotes: dict[str, QuoteSnapshot],
    spec: RankDefinition,
) -> list[str] | None:
    rows: list[dict[str, float | str]] = []
    sort_col = spec.sort_column or spec.redis_field
    for tf_symbol in tf_symbols:
        quote = quotes.get(tf_symbol)
        if quote is None or quote.last_price <= 0:
            continue
        if not quote_matches_rank(quote, spec):
            continue
        row: dict[str, float | str] = {
            "tf_symbol": tf_symbol,
            "_sort_value": quote_rank_value(quote, sort_col),
        }
        rows.append(row)

    if not rows:
        return []

    df = pl.DataFrame(rows)
    sorted_df = df.sort("_sort_value", descending=not spec.ascending, nulls_last=True)
    return sorted_df["tf_symbol"].cast(pl.Utf8).to_list()
