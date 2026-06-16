"""自选多维看盘数据加载。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar.radar_models import merge_row_quotes
from vnpy_ashare.quotes.radar.radar_pool import name_map_for_symbols
from vnpy_ashare.quotes.radar.radar_watchlist import (
    _intraday_score,
    _quotes_for_candidates,
    _watchlist_metric,
)
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiBoardData, WatchlistMultiRow
from vnpy_ashare.quotes.watchlist_multiview.sort import sort_multiview_rows
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


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
    for index, (symbol, exchange, _name) in enumerate(watchlist):
        vt_symbol = f"{symbol}.{exchange.value}"
        candidates.append(vt_symbol)
        sort_orders[vt_symbol] = index

    quotes_by_vt = _quotes_for_candidates(candidates)
    try:
        from vnpy_ashare.quotes.radar.radar_moneyflow import enrich_quotes_with_moneyflow

        quotes_by_vt = enrich_quotes_with_moneyflow(quotes_by_vt)
    except Exception:
        pass

    name_map = name_map_for_symbols(candidates)
    changes = [float(merge_row_quotes(quotes_by_vt.get(vt, {})).get("change_pct") or 0) for vt in candidates if quotes_by_vt.get(vt)]
    pool_median = sorted(changes)[len(changes) // 2] if changes else 0.0

    rows: list[WatchlistMultiRow] = []
    for vt_symbol in candidates:
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        raw = quotes_by_vt.get(vt_symbol, {"vt_symbol": vt_symbol})
        merged = merge_row_quotes(raw)
        name = str(merged.get("name") or name_map.get(vt_symbol) or item.name or vt_symbol)
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
                change_pct=_float_or_none(merged.get("change_pct")),
                volume_ratio=_float_or_none(merged.get("volume_ratio")),
                turnover_rate=_float_or_none(merged.get("turnover_rate")),
                change_speed_5m=_float_or_none(merged.get("change_speed_5m")),
                metric_label=metric_label,
                metric_value=metric_value,
                sub_label=sub_label,
                sub_value=sub_value,
                anomaly_score=_intraday_score(raw, pool_median_change=pool_median),
            )
        )

    key = sort_key if sort_key in ("sort_order", "change_pct", "anomaly_score") else "sort_order"
    sorted_rows = sort_multiview_rows(rows, sort_key=key)
    return WatchlistMultiBoardData(
        rows=tuple(sorted_rows),
        empty_message="",
        total_count=len(sorted_rows),
    )
