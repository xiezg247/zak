"""刷新情绪周期芯片（市场 / 雷达 / 自选共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_chip import EmotionCycleChip


def refresh_emotion_cycle_chip(chip: EmotionCycleChip) -> None:
    from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot

    chip.render(load_emotion_cycle_snapshot())
