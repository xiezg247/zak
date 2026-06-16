"""5 分钟涨速：Redis 基准价滚动窗口。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot

SPEED_BASELINE_HASH_KEY = "zak:speed:baseline"
SPEED_BASELINE_AT_KEY = "zak:meta:speed_baseline_at"
SPEED_WINDOW_SEC = 300


def compute_change_speed_5m(current_price: float, baseline_price: float) -> float:
    if current_price <= 0 or baseline_price <= 0:
        return 0.0
    return (current_price - baseline_price) / baseline_price * 100.0


def apply_change_speed_5m(client, quotes: dict[str, QuoteSnapshot]) -> None:
    """就地写入 change_speed_5m，并按窗口滚动基准价 HASH。"""
    if not quotes:
        return

    now = time.time()
    baseline_at_raw = client.get(SPEED_BASELINE_AT_KEY)
    try:
        baseline_at = float(baseline_at_raw) if baseline_at_raw else 0.0
    except (TypeError, ValueError):
        baseline_at = 0.0

    baselines = client.hgetall(SPEED_BASELINE_HASH_KEY) or {}
    should_rotate = not baselines or (now - baseline_at) >= SPEED_WINDOW_SEC

    if baselines:
        for tf_symbol, quote in quotes.items():
            try:
                base = float(baselines.get(tf_symbol, 0) or 0)
            except (TypeError, ValueError):
                base = 0.0
            quote.change_speed_5m = compute_change_speed_5m(quote.last_price, base)
    else:
        for quote in quotes.values():
            quote.change_speed_5m = 0.0

    if not should_rotate:
        return

    mapping = {tf_symbol: str(quote.last_price) for tf_symbol, quote in quotes.items() if quote.last_price > 0}
    pipe = client.pipeline(transaction=False)
    pipe.delete(SPEED_BASELINE_HASH_KEY)
    if mapping:
        pipe.hset(SPEED_BASELINE_HASH_KEY, mapping=mapping)
    pipe.set(SPEED_BASELINE_AT_KEY, str(now))
    pipe.execute()
