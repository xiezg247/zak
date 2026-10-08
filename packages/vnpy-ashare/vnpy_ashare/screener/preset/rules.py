"""选股规则（行情 / Tushare 基本面）。

行情 preset 对 ``quotes`` 行排序/过滤；Tushare preset 对 ``daily_basic`` / ``moneyflow`` 行筛选。
"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, QuoteRowsLike, quote_row_copy
from vnpy_ashare.screener.engine.row_normalize import normalize_quote_row
from vnpy_ashare.screener.hard_filters import apply_recipe_filters

# Tushare daily_basic.total_mv 单位为万元；50 亿 = 500000 万元
MIN_TOTAL_MV_50YI = 500_000.0
STRONG_UP_MIN_CHANGE_PCT = 5.0


def apply_quote_preset(
    preset: str,
    quotes: QuoteRowsLike,
    *,
    top_n: int = 20,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_turnover: float | None = None,
) -> list[QuoteRow]:
    """对行情行应用 preset 规则，返回标准化结果行（最多 top_n 条）。"""
    preset = preset.strip()
    top_n = max(1, min(int(top_n or 20), 200))
    quotes = apply_recipe_filters(quotes)

    from vnpy_ashare.screener.engine.presets import sort_quote_rows_polars

    sorted_quotes = sort_quote_rows_polars(
        quotes,
        preset=preset,
        top_n=top_n,
        min_change_pct=min_change_pct,
        max_change_pct=max_change_pct,
        min_turnover=min_turnover,
    )
    return [normalize_quote_row(q) for q in sorted_quotes]


def apply_low_pe(rows: QuoteRowsLike, *, top_n: int, max_pe_ttm: float = 15.0) -> list[QuoteRow]:
    """PE(TTM) 在 (0, max_pe_ttm) 内升序取 top_n。"""
    rows = apply_recipe_filters(rows)
    filtered = [row for row in rows if row.get("pe_ttm", 0) > 0 and row.get("pe_ttm", 0) < max_pe_ttm]
    filtered.sort(key=lambda r: r.get("pe_ttm", 0))
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_large_cap(
    rows: QuoteRowsLike,
    *,
    top_n: int,
    min_total_mv: float = MIN_TOTAL_MV_50YI,
) -> list[QuoteRow]:
    """总市值 ≥ min_total_mv（默认 50 亿）降序取 top_n。"""
    rows = apply_recipe_filters(rows)
    filtered = [row for row in rows if row.get("total_mv", 0) >= min_total_mv]
    filtered.sort(key=lambda r: r.get("total_mv", 0), reverse=True)
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_limit_up(rows: QuoteRowsLike, *, top_n: int) -> list[QuoteRow]:
    """涨停列表按连板次数降序取 top_n。"""
    rows = apply_recipe_filters(rows)
    sorted_rows = sorted(rows, key=lambda r: float(r.get("limit_times") or 0), reverse=True)
    return [_limit_up_row(r) for r in sorted_rows[:top_n]]


def apply_moneyflow_in(rows: QuoteRowsLike, *, top_n: int) -> list[QuoteRow]:
    """主力净流入 > 0 降序取 top_n。"""
    from vnpy_ashare.screener.engine.dimensions.moneyflow_in import apply_moneyflow_in_polars

    return apply_moneyflow_in_polars(list(rows), top_n=top_n)


def _limit_up_row(row: QuoteRowLike) -> QuoteRow:
    vt_symbol = str(row.get("vt_symbol") or "")
    symbol = vt_symbol.split(".")[0] if vt_symbol else ""
    return quote_row_copy(
        row,
        symbol=symbol,
        name=str(row.get("name") or ""),
        vt_symbol=vt_symbol,
        limit_times=float(row.get("limit_times") or 0),
        limit=str(row.get("limit") or ""),
        trade_date=str(row.get("trade_date") or ""),
        source="tushare",
    )


def _fundamental_row(row: QuoteRowLike) -> QuoteRow:
    return quote_row_copy(
        row,
        symbol=str(row.get("symbol") or ""),
        name=str(row.get("name") or ""),
        vt_symbol=str(row.get("vt_symbol") or ""),
        close=float(row.get("close") or 0),
        pe_ttm=float(row.get("pe_ttm") or 0),
        pb=float(row.get("pb") or 0),
        total_mv=float(row.get("total_mv") or 0),
        circ_mv=float(row.get("circ_mv") or 0),
        turnover_rate=float(row.get("turnover_rate") or 0),
        trade_date=str(row.get("trade_date") or ""),
        source=str(row.get("source") or "tushare"),
    )
