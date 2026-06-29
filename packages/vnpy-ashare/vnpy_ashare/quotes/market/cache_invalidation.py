"""行情行缓存更新后的下游失效链（打破 store ↔ emotion_cycle 循环依赖）。"""

from __future__ import annotations

from vnpy_ashare.quotes.market.emotion_cycle_cache import invalidate_emotion_cycle_cache
from vnpy_ashare.quotes.radar.radar_card_snapshot_cache import invalidate_radar_card_snapshots
from vnpy_ashare.quotes.radar.radar_leader_pool_cache import invalidate_leader_candidate_pool


def on_market_quotes_updated() -> None:
    invalidate_emotion_cycle_cache()
    invalidate_leader_candidate_pool()
    invalidate_radar_card_snapshots()
