"""行情行缓存更新后的下游失效链（打破 store ↔ emotion_cycle 循环依赖）。"""

from __future__ import annotations

from vnpy_ashare.quotes.market.emotion_cycle_cache import invalidate_emotion_cycle_cache
from vnpy_ashare.quotes.market.market_summary_cache import invalidate_limit_ladder_cache


def on_market_quotes_updated() -> None:
    invalidate_emotion_cycle_cache()
    invalidate_limit_ladder_cache()
