"""自选多维看盘排序。"""

from __future__ import annotations

from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiRow, WatchlistMultiSortKey


def sort_multiview_rows(
    rows: list[WatchlistMultiRow],
    *,
    sort_key: WatchlistMultiSortKey,
) -> list[WatchlistMultiRow]:
    if sort_key == "sort_order":
        return sorted(rows, key=lambda row: (row.sort_order, row.symbol))
    if sort_key == "change_pct":
        return sorted(
            rows,
            key=lambda row: (row.change_pct if row.change_pct is not None else float("-inf")),
            reverse=True,
        )
    return sorted(rows, key=lambda row: row.anomaly_score, reverse=True)
