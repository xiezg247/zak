"""恐贪指数拉取（经 SentimentService，engine 启动后 bind）。"""

from __future__ import annotations

from vnpy_ashare.domain.sentiment.fear_greed import FearGreedSnapshot
from vnpy_ashare.services.sentiment import bind_sentiment_service, try_compute_fear_greed

__all__ = ["bind_sentiment_service", "try_fetch_fear_greed_index"]


def try_fetch_fear_greed_index(
    *,
    include_components: bool = False,
    trade_date: str | None = None,
) -> FearGreedSnapshot | None:
    return try_compute_fear_greed(
        include_components=include_components,
        trade_date=trade_date,
    )
