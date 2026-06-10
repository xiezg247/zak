"""市场页全量排序与展示切片（纯函数，便于测试）。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot


def sort_market_items(
    items: list[StockItem],
    *,
    sort_column: str | None,
    ascending: bool,
    catalog: list[StockItem],
    quote_map: dict[str, QuoteSnapshot],
    sort_key_fn: Callable[[str, StockItem, QuoteSnapshot | None, str], float | str],
) -> list[StockItem]:
    if not sort_column or not items:
        return list(items)

    reverse = not ascending
    if sort_column == "index":
        catalog_index = {(item.symbol, item.exchange): index for index, item in enumerate(catalog)}
        return sorted(
            items,
            key=lambda item: catalog_index.get((item.symbol, item.exchange), 0),
            reverse=reverse,
        )

    return sorted(
        items,
        key=lambda item: sort_key_fn(
            sort_column,
            item,
            quote_map.get(item.tickflow_symbol),
            "",
        ),
        reverse=reverse,
    )


def paginate_market_page(
    items: list[StockItem],
    *,
    page: int,
    page_size: int,
) -> list[StockItem]:
    size = max(page_size, 1)
    start = max(page, 0) * size
    return list(items[start : start + size])


def slice_market_display(
    items: list[StockItem],
    *,
    live_mode: bool,
    page: int = 0,
    page_size: int = 100,
    live_display_limit: int = 100,
) -> list[StockItem]:
    if not live_mode:
        return list(items)
    size = max(page_size or live_display_limit, 1)
    return paginate_market_page(items, page=page, page_size=size)
