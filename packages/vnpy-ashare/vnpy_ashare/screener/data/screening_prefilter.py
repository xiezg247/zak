"""选股上下文快照预过滤：粗筛 / 板块白名单 / 配方硬过滤 / 恐贪缩池。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.domain.market.quote_row import coerce_quote_rows
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot

if TYPE_CHECKING:
    from vnpy_ashare.screener.data.screening_context import ScreeningContext


def at_any_limit_board(symbol: str, change_pct: float) -> bool:
    """涨跌停或接近涨跌停（主板 ±9.8%，科创/创业板 ±19.5%）。"""
    if symbol.startswith(("300", "688")):
        return abs(change_pct) >= 19.5
    return abs(change_pct) >= 9.8


def is_beijing_board(symbol: str) -> bool:
    """北交所主板（4/8开头）。"""
    return bool(symbol) and symbol[0] in ("4", "8")


def get_board_prefilter_boards() -> frozenset[str]:
    """粗筛用板块白名单（与硬过滤共享 RECIPE_ALLOWED_MARKET_BOARDS 配置）。"""
    from vnpy_ashare.screener.hard_filters import resolve_market_board_filter

    board_filter = resolve_market_board_filter()
    return board_filter.boards if board_filter.active else frozenset()


def passes_board_prefilter(symbol: str) -> bool:
    """板块粗筛：symbol 前缀是否命中配置的市场板块白名单。"""
    boards = get_board_prefilter_boards()
    if not boards:
        return True
    from vnpy_ashare.domain.market.board import matches_board

    return any(matches_board(symbol, board) for board in boards)


def apply_coarse_quote_filters(rows: list) -> list:
    """纯行内字段过滤，不发起任何外部请求。"""
    from vnpy_ashare.screener.hard_filters import recipe_min_amount_yuan

    min_amount = recipe_min_amount_yuan()
    kept: list = []
    for row in rows:
        last_price = float(row.get("last_price") or 0)
        if last_price <= 0:
            continue

        change_pct = float(row.get("change_pct") or 0)
        symbol = str(row.get("symbol") or "")
        if at_any_limit_board(symbol, change_pct):
            continue

        if min_amount > 0:
            amount = float(row.get("amount") or 0)
            if amount < min_amount:
                continue

        if is_beijing_board(symbol):
            continue

        symbol_col = str(row.get("symbol") or "")
        if not passes_board_prefilter(symbol_col):
            continue

        kept.append(row)
    return kept


def apply_board_prefilter_rows(rows: list) -> list:
    """公共工具：按 RECIPE_ALLOWED_MARKET_BOARDS 配置过滤行列表。

    盘中/盘后维度均可调用，不依赖 ScreeningContext。
    """
    boards = get_board_prefilter_boards()
    if not boards:
        return rows
    return [
        row
        for row in rows
        if passes_board_prefilter(str(row.get("symbol") or row.get("vt_symbol", "") or "").split(".")[0])
    ]


def replace_context_snapshot(ctx: ScreeningContext, *, rows: list, total: int | None = None) -> None:
    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None:
        return
    ctx._snapshot = MarketQuotesSnapshot(
        rows=coerce_quote_rows(rows),
        updated_at=snapshot.updated_at,
        total=len(rows) if total is None else total,
        source=snapshot.source,
    )
    # 快照行变更后 Polars frame 必须失效，避免沿用旧全表
    ctx._snapshot_frame = None


def apply_coarse_quote_filters_polars(rows: list) -> list:
    """粗筛的 Polars 向量化实现（与 ``apply_coarse_quote_filters`` 语义对齐）。"""
    if not rows:
        return []
    try:
        import polars as pl
    except ImportError:
        return apply_coarse_quote_filters(rows)

    from vnpy_ashare.domain.market.board import BOARD_PREFIXES
    from vnpy_ashare.screener.engine.frame import restore_rows, rows_with_index
    from vnpy_ashare.screener.hard_filters import recipe_min_amount_yuan

    payloads, _ = rows_with_index(rows)
    df = pl.DataFrame(payloads, infer_schema_length=max(len(payloads), 1))
    for col in ("symbol", "vt_symbol", "last_price", "change_pct", "amount"):
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    symbol = pl.coalesce(
        pl.col("symbol").cast(pl.Utf8, strict=False),
        pl.col("vt_symbol").cast(pl.Utf8, strict=False).str.split(".").list.first(),
    ).fill_null("")
    last_price = pl.col("last_price").cast(pl.Float64, strict=False).fill_null(0.0)
    change_pct = pl.col("change_pct").cast(pl.Float64, strict=False).fill_null(0.0)
    amount = pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0)

    is_growth = symbol.str.starts_with("300") | symbol.str.starts_with("688")
    limit_thr = pl.when(is_growth).then(pl.lit(19.5)).otherwise(pl.lit(9.8))
    min_amount = recipe_min_amount_yuan()
    mask = (last_price > 0) & (change_pct.abs() < limit_thr) & ~symbol.str.slice(0, 1).is_in(["4", "8"])
    if min_amount > 0:
        mask = mask & (amount >= min_amount)

    boards = get_board_prefilter_boards()
    if boards:
        board_exprs = []
        for board in boards:
            prefixes = BOARD_PREFIXES.get(board) or ()
            if prefixes:
                board_exprs.append(pl.any_horizontal([symbol.str.starts_with(p) for p in prefixes]))
        if board_exprs:
            mask = mask & pl.any_horizontal(board_exprs)

    filtered_df = df.filter(mask)
    if filtered_df.height == len(rows):
        return rows
    return restore_rows(rows, filtered_df.to_dicts())


def coarse_prefilter_snapshot(ctx: ScreeningContext) -> None:
    """粗筛：仅用行情快照字段（零 API 调用）先过滤无效/涨跌停/低流动性/北交所标的。"""
    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None or not getattr(snapshot, "rows", None):
        return
    rows = list(snapshot.rows)
    original = len(rows)
    filtered = apply_coarse_quote_filters_polars(rows)
    if len(filtered) == original:
        return
    replace_context_snapshot(ctx, rows=filtered)


def apply_recipe_prefilter_to_context(ctx: ScreeningContext) -> None:
    """将配方硬过滤（含 RECIPE_ALLOWED / ASHARE_TRADING_BOARDS）应用到上下文行情快照。"""
    from vnpy_ashare.screener.hard_filters import apply_recipe_filters

    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None or not getattr(snapshot, "rows", None):
        return
    filtered = apply_recipe_filters(list(snapshot.rows))
    if len(filtered) == len(snapshot.rows):
        return
    replace_context_snapshot(ctx, rows=filtered)


def apply_sentiment_prefilter_to_context(ctx: ScreeningContext) -> None:
    """恐贪前置缩池应用到上下文行情快照。"""
    from vnpy_ashare.screener.sentiment.snapshot_prefilter import apply_sentiment_snapshot_prefilter

    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None or not getattr(snapshot, "rows", None):
        return
    filtered = apply_sentiment_snapshot_prefilter(list(snapshot.rows))
    if len(filtered) == len(snapshot.rows):
        return
    replace_context_snapshot(ctx, rows=filtered)


def prefilter_snapshot(ctx: ScreeningContext) -> None:
    """提前应用硬过滤（ST、停牌、流动性），减少后续维度和 DataFrame 规模。"""
    apply_recipe_prefilter_to_context(ctx)
