"""雷达卡片布局常量与纯展示辅助（无 Qt）。"""

from __future__ import annotations

RADAR_ROW_LAYOUT_HEIGHT = 34
RADAR_ROW_SPACING = 3
RADAR_CARD_CHROME_HEIGHT = 108

BODY_PAGE_ROWS = 0
BODY_PAGE_EMPTY = 1


def estimate_card_min_height(top_n: int) -> int:
    """按展示条数估算卡片最小高度，避免列表区被压扁。"""
    rows = max(1, int(top_n))
    body = rows * RADAR_ROW_LAYOUT_HEIGHT + max(0, rows - 1) * RADAR_ROW_SPACING
    return RADAR_CARD_CHROME_HEIGHT + body


def card_frame_object_name(*, mode: str, supports_auto_refresh: bool) -> str:
    """卡片根节点 objectName（主题区分统计/展望/实时/手动）。"""
    if mode == "predictive":
        return "RadarCardPredictive"
    if supports_auto_refresh:
        return "RadarCardLive"
    return "RadarCardManual"


def kind_badge_presentation(mode: str) -> tuple[str, str]:
    """返回 (文案, objectName)。"""
    if mode == "statistical":
        return "统计", "RadarCardKindBadgeStatistical"
    return "展望", "RadarCardKindBadgePredictive"


def mode_badge_presentation(
    *,
    supports_auto_refresh: bool,
    phase: str,
    phase_label: str,
) -> tuple[str, str]:
    """返回 (文案, objectName)。"""
    if not supports_auto_refresh:
        return "手动", "RadarCardModeBadgeOff"
    object_name = "RadarCardModeBadgeLive" if phase == "intraday" else "RadarCardModeBadgeOff"
    return phase_label, object_name


def format_card_meta(*, updated_at_text: str, card_resonance: int) -> str:
    """页脚 meta：更新时间 · 共振数。"""
    parts: list[str] = []
    if updated_at_text:
        parts.append(updated_at_text)
    if card_resonance:
        parts.append(f"共振 {card_resonance}")
    return " · ".join(parts)


def count_resonance_hits(
    vt_symbols: list[str] | tuple[str, ...],
    resonance_counts: dict[str, int],
    *,
    threshold: int = 2,
) -> int:
    """统计共振次数 ≥ threshold 的标的数。"""
    return sum(1 for vt in vt_symbols if resonance_counts.get(vt, 0) >= threshold)


def fallback_visible_card_ids(card_ids: list[str] | tuple[str, ...], columns: int) -> list[str]:
    """视口不可用时回退首行卡片 id。"""
    n = max(1, int(columns))
    return list(card_ids[:n])
