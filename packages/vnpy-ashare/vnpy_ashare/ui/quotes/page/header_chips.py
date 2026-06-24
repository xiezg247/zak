"""行情页顶栏情绪周期芯片刷新。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_refresh import refresh_emotion_cycle_chip


def refresh_emotion_cycle_chip_for_page(page: Any) -> None:
    chip = getattr(page, "emotion_cycle_chip", None)
    if chip is None:
        return
    refresh_emotion_cycle_chip(chip)


def refresh_header_chips_for_page(page: Any) -> None:
    refresh_emotion_cycle_chip_for_page(page)
