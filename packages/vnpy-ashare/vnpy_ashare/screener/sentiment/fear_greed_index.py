"""恐贪指数独立拉取实现（启动时注册到 fear_greed_provider）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.screener.sentiment.fear_greed_provider import register_fear_greed_fetcher
from vnpy_ashare.services.sentiment_service import SentimentService

if TYPE_CHECKING:
    from vnpy_ashare.services.sentiment_service import FearGreedSnapshot


def _fetch_fear_greed_index(*, include_components: bool = False) -> FearGreedSnapshot | None:
    try:
        svc = SentimentService.__new__(SentimentService)
        svc._cache = {}
        return SentimentService.compute_fear_greed(svc, include_components=include_components)
    except Exception:
        return None


def try_fetch_fear_greed_index(*, include_components: bool = False) -> FearGreedSnapshot | None:
    return _fetch_fear_greed_index(include_components=include_components)


register_fear_greed_fetcher(_fetch_fear_greed_index)
