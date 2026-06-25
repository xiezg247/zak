"""自选多维看盘数据加载。"""

from __future__ import annotations

from typing import Any, cast

from vnpy_ashare.domain.core.numbers import float_or_none
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.quotes.radar.radar_models import merge_row_quotes
from vnpy_ashare.quotes.radar.radar_moneyflow import enrich_quotes_with_moneyflow
from vnpy_ashare.quotes.radar.radar_watchlist import (
    _intraday_score,
    _quotes_for_candidates,
    _watchlist_metric,
)
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiBoardData, WatchlistMultiRow, WatchlistMultiSortKey
from vnpy_ashare.quotes.watchlist_multiview.sort import sort_multiview_rows
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows


def _quote_row_from_snapshot(item: StockItem, quote: QuoteSnapshot | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "vt_symbol": item.vt_symbol,
        "symbol": item.symbol,
        "name": item.name or "",
    }
    if quote is None:
        return row
    row.update(
        {
            "name": item.name or quote.name or "",
            "last_price": quote.last_price,
            "close": quote.last_price,
            "change_pct": quote.change_pct,
            "change_amount": quote.change_amount,
            "turnover_rate": quote.turnover_rate,
            "volume_ratio": quote.volume_ratio,
            "net_mf_amount": quote.net_mf_amount,
            "change_speed_5m": quote.change_speed_5m,
            "volume": quote.volume,
            "amount": quote.amount,
        }
    )
    return row


def _assemble_multiview_board(
    candidates: list[str],
    sort_orders: dict[str, int],
    quotes_by_vt: dict[str, dict[str, Any]],
    *,
    sort_key: str,
    empty_message: str = "",
    name_by_vt: dict[str, str] | None = None,
) -> WatchlistMultiBoardData:
    if not candidates:
        return WatchlistMultiBoardData(rows=(), empty_message=empty_message, total_count=0)

    stored_names = name_by_vt or {}
    changes = [float(merge_row_quotes(quotes_by_vt.get(vt, {})).get("change_pct") or 0) for vt in candidates if quotes_by_vt.get(vt)]
    pool_median = sorted(changes)[len(changes) // 2] if changes else 0.0

    rows: list[WatchlistMultiRow] = []
    for vt_symbol in candidates:
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        raw = quotes_by_vt.get(vt_symbol, {"vt_symbol": vt_symbol})
        merged = merge_row_quotes(raw)
        name = str(stored_names.get(vt_symbol) or merged.get("name") or item.name or vt_symbol)
        price_raw = merged.get("last_price") or merged.get("close")
        last_price = float(price_raw) if isinstance(price_raw, (int, float)) and float(price_raw) > 0 else None
        metric_label, metric_value, sub_label, sub_value = _watchlist_metric(merged)
        rows.append(
            WatchlistMultiRow(
                vt_symbol=vt_symbol,
                symbol=item.symbol,
                name=name,
                sort_order=sort_orders.get(vt_symbol, 0),
                last_price=last_price,
                change_pct=float_or_none(merged.get("change_pct")),
                volume_ratio=float_or_none(merged.get("volume_ratio")),
                turnover_rate=float_or_none(merged.get("turnover_rate")),
                change_speed_5m=float_or_none(merged.get("change_speed_5m")),
                metric_label=metric_label,
                metric_value=metric_value,
                sub_label=sub_label,
                sub_value=sub_value,
                anomaly_score=_intraday_score(raw, pool_median_change=pool_median),
            )
        )

    key = cast(
        WatchlistMultiSortKey,
        sort_key if sort_key in ("sort_order", "change_pct", "anomaly_score") else "sort_order",
    )
    sorted_rows = sort_multiview_rows(rows, sort_key=key)
    return WatchlistMultiBoardData(
        rows=tuple(sorted_rows),
        empty_message=empty_message,
        total_count=len(sorted_rows),
    )


def build_watchlist_multiview_board_from_page(
    *,
    stocks: list[StockItem],
    quote_map: dict[str, QuoteSnapshot],
    sort_key: str = "sort_order",
    refresh_moneyflow: bool = False,
) -> WatchlistMultiBoardData:
    """从自选页内存行情构建多维看板（避免 tick 级重复 I/O）。"""
    if not stocks:
        return WatchlistMultiBoardData(rows=(), empty_message="自选池为空，请先添加自选。", total_count=0)

    candidates = [item.vt_symbol for item in stocks]
    sort_orders = {item.vt_symbol: index for index, item in enumerate(stocks)}
    name_by_vt = {item.vt_symbol: item.name or "" for item in stocks}
    quotes_by_vt = {item.vt_symbol: _quote_row_from_snapshot(item, quote_map.get(item.tickflow_symbol)) for item in stocks}
    if refresh_moneyflow:
        try:
            quotes_by_vt = enrich_quotes_with_moneyflow(quotes_by_vt)
        except Exception:
            pass
    return _assemble_multiview_board(
        candidates,
        sort_orders,
        quotes_by_vt,
        sort_key=sort_key,
        name_by_vt=name_by_vt,
    )


def build_watchlist_multiview_board(
    *,
    sort_key: str = "sort_order",
    vt_symbols: tuple[str, ...] | None = None,
) -> WatchlistMultiBoardData:
    watchlist = load_watchlist_rows()
    if vt_symbols is not None:
        allowed = set(vt_symbols)
        watchlist = [row for row in watchlist if f"{row[0]}.{row[1].value}" in allowed]
    if not watchlist:
        return WatchlistMultiBoardData(rows=(), empty_message="自选池为空，请先添加自选。", total_count=0)

    candidates: list[str] = []
    sort_orders: dict[str, int] = {}
    name_by_vt: dict[str, str] = {}
    for index, (symbol, exchange, name) in enumerate(watchlist):
        vt_symbol = f"{symbol}.{exchange.value}"
        candidates.append(vt_symbol)
        sort_orders[vt_symbol] = index
        name_by_vt[vt_symbol] = name or ""

    quotes_by_vt = _quotes_for_candidates(candidates)
    try:
        quotes_by_vt = enrich_quotes_with_moneyflow(quotes_by_vt)
    except Exception:
        pass

    return _assemble_multiview_board(
        candidates,
        sort_orders,
        quotes_by_vt,
        sort_key=sort_key,
        name_by_vt=name_by_vt,
    )
