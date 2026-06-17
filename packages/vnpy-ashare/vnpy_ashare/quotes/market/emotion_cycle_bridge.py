"""情绪周期快照懒加载（打破 sentiment_gate ↔ emotion_cycle 循环）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot


def try_load_emotion_cycle_snapshot() -> Any | None:
    try:
        return load_emotion_cycle_snapshot(fetch_if_missing=True)
    except Exception:
        return None
