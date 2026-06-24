"""跨卡共振汇总与风险标的收集。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.radar.radar_catalog import radar_card_mode, radar_card_resonance_weight
from vnpy_ashare.quotes.radar.radar_market_emotion import is_stat_row
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarResonanceEntry, RadarRow
from vnpy_ashare.quotes.radar.radar_resonance_prefs import radar_card_participates_in_resonance


def accumulate_radar_resonance(
    payload: dict[str, RadarCardData],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for data in payload.values():
        if not radar_card_participates_in_resonance(data.card_id):
            continue
        card_weight = radar_card_resonance_weight(data.card_id)
        if card_weight <= 0:
            continue
        seen_in_card: set[str] = set()
        for row in data.rows:
            if is_stat_row(row.vt_symbol):
                continue
            if row.vt_symbol in seen_in_card:
                continue
            seen_in_card.add(row.vt_symbol)
            bucket = grouped.setdefault(
                row.vt_symbol,
                {"row": row, "titles": [], "card_count": 0, "weight_score": 0.0},
            )
            titles = bucket["titles"]
            assert isinstance(titles, list)
            titles.append(data.title)
            bucket["card_count"] = int(bucket.get("card_count") or 0) + 1
            bucket["weight_score"] = float(bucket.get("weight_score") or 0.0) + card_weight
            bucket["row"] = row
    return grouped


def build_radar_resonance_list(
    payload: dict[str, RadarCardData],
    *,
    min_cards: int = 2,
    mode: str | None = None,
) -> tuple[RadarResonanceEntry, ...]:
    """汇总跨卡共振标的，按加权分降序。

    mode 为 statistical / predictive 时仅统计对应分区卡片。
    """
    if mode is not None:
        payload = {card_id: data for card_id, data in payload.items() if radar_card_mode(card_id) == mode}
    grouped = accumulate_radar_resonance(payload)
    entries: list[RadarResonanceEntry] = []
    for vt_symbol, bucket in grouped.items():
        titles = bucket["titles"]
        assert isinstance(titles, list)
        card_count = int(bucket.get("card_count") or 0)
        if card_count < min_cards:
            continue
        row = bucket["row"]
        assert isinstance(row, RadarRow)
        weight_score = round(float(bucket.get("weight_score") or 0.0), 2)
        entries.append(
            RadarResonanceEntry(
                vt_symbol=vt_symbol,
                name=row.name,
                symbol=row.symbol,
                card_count=card_count,
                card_titles=tuple(titles),
                price=row.price,
                change_pct=row.change_pct,
                resonance_score=weight_score,
            )
        )
    entries.sort(
        key=lambda item: (
            -item.resonance_score,
            -item.card_count,
            item.vt_symbol,
        ),
    )
    return tuple(entries)


def build_radar_resonance_ai_prompt(payload: dict[str, RadarCardData]) -> str:
    """生成仅针对共振标的的 AI 解读预填文案。"""
    entries = build_radar_resonance_list(payload)
    if not entries:
        return ""
    lines = [
        "请重点解读以下雷达共振标的（同时出现在多张卡片）：",
        "1. 共振原因与共性特征",
        "2. 优先关注顺序与风险提示",
        "3. 不要编造未出现在数据中的价格或指标",
        "",
    ]
    for entry in entries:
        price = f"{entry.price:.2f}" if entry.price is not None else "—"
        change = f"{entry.change_pct:+.2f}%" if entry.change_pct is not None else "—"
        cards = "、".join(entry.card_titles)
        score_note = f" · 加权 {entry.resonance_score:.1f}" if entry.resonance_score > 0 else ""
        lines.append(f"- {entry.name}({entry.symbol}) {change} 现价{price} · {entry.card_count}卡{score_note}：{cards}")
    return "\n".join(lines)


def compute_radar_resonance(payload: dict[str, RadarCardData], *, min_cards: int = 2, mode: str | None = None) -> dict[str, int]:
    """统计在多张卡片中出现的标的（共振卡数）。"""
    if mode is not None:
        payload = {card_id: data for card_id, data in payload.items() if radar_card_mode(card_id) == mode}
    grouped = accumulate_radar_resonance(payload)
    return {vt_symbol: int(bucket.get("card_count") or 0) for vt_symbol, bucket in grouped.items() if int(bucket.get("card_count") or 0) >= min_cards}


def compute_radar_resonance_scores(
    payload: dict[str, RadarCardData],
    *,
    min_cards: int = 2,
) -> dict[str, float]:
    """共振加权分（发现卡权重高于选股缓存）。"""
    grouped = accumulate_radar_resonance(payload)
    return {
        vt_symbol: round(float(bucket.get("weight_score") or 0.0), 2)
        for vt_symbol, bucket in grouped.items()
        if int(bucket.get("card_count") or 0) >= min_cards
    }


def collect_radar_risk_vt_symbols(payload: dict[str, RadarCardData]) -> frozenset[str]:
    """炸板断板风险卡中的标的（供共振侧栏提示）。"""
    data = payload.get("discovery_limit_break")
    if data is None:
        return frozenset()
    return frozenset(str(row.vt_symbol).strip() for row in data.rows if str(row.vt_symbol or "").strip() and not is_stat_row(row.vt_symbol))
