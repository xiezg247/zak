"""个股新闻：AKShare 主源。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.akshare.events import (
    AkshareFetchError,
    AkshareNotInstalledError,
    fetch_stock_news_akshare,
)


class NewsFetchError(RuntimeError):
    """新闻数据源不可用。"""


def fetch_stock_news(ts_code: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """拉取个股近期新闻。"""
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []

    try:
        return fetch_stock_news_akshare(ts_code, limit=limit)
    except AkshareNotInstalledError as ex:
        raise NewsFetchError(str(ex)) from ex
    except AkshareFetchError as ex:
        raise NewsFetchError(str(ex)) from ex
