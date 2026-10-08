"""雷达盘中刷新与权重重载计划（纯函数）。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from vnpy_ashare.quotes.radar.loaders import RadarCardData
from vnpy_ashare.quotes.radar.radar_market_emotion import is_stat_row
from vnpy_ashare.quotes.radar.radar_resonance_prefs import DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS


def live_quote_refresh_candidates(
    payload: Mapping[str, RadarCardData],
    card_ids: Sequence[str],
) -> list[tuple[str, RadarCardData]]:
    """筛选需要盘中刷现价/涨幅的卡片（跳过纯统计行）。"""
    pending: list[tuple[str, RadarCardData]] = []
    for card_id in card_ids:
        data = payload.get(card_id)
        if data is None or not data.rows:
            continue
        if all(is_stat_row(row.vt_symbol) for row in data.rows):
            continue
        pending.append((card_id, data))
    return pending


def should_run_card_auto_refresh(*, visible: bool, interval_ms: int, in_session: bool) -> bool:
    """当前卡是否应保持自动刷新定时器运行。"""
    return bool(visible and interval_ms > 0 and in_session)


def reload_ids_after_resonance_weight_change(
    payload_card_ids: Iterable[str],
    *,
    weight_card_ids: Iterable[str] = DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS,
) -> list[str]:
    """权重变更后需强制重算的卡片（跳过展望卡缓存）。"""
    present = set(payload_card_ids)
    return [
        card_id
        for card_id in weight_card_ids
        if card_id in present and not card_id.startswith("outlook_")
    ]
