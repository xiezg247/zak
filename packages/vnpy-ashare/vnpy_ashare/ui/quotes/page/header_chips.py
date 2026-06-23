"""行情页顶栏情绪周期 / 风控闸芯片刷新。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_refresh import refresh_emotion_cycle_chip
from vnpy_ashare.ui.quotes.market_overview.risk_gate_refresh import refresh_risk_gate_chip
from vnpy_ashare.ui.quotes.watchlist_positions.risk_settings_dialog import RiskSettingsDialog

if TYPE_CHECKING:
    pass


def refresh_emotion_cycle_chip_for_page(page: Any) -> None:
    chip = getattr(page, "emotion_cycle_chip", None)
    if chip is None:
        return
    refresh_emotion_cycle_chip(chip)


def refresh_risk_gate_chip_for_page(page: Any) -> None:
    chip = getattr(page, "risk_gate_chip", None)
    if chip is None:
        return
    refresh_risk_gate_chip(chip, page=page)


def open_risk_settings_for_page(page: Any) -> None:
    cache = getattr(page, "position_cache", None)
    position_cache = cache if isinstance(cache, dict) else None
    if RiskSettingsDialog.open_and_save(
        page,
        position_cache=position_cache,
        on_prefs_changed=lambda: refresh_risk_gate_chip_for_page(page),
    ):
        refresh_risk_gate_chip_for_page(page)


def refresh_header_chips_for_page(page: Any) -> None:
    refresh_emotion_cycle_chip_for_page(page)
    refresh_risk_gate_chip_for_page(page)
