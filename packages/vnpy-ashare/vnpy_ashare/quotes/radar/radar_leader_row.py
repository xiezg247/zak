"""LeaderScoredRow → 雷达行展示模型。"""

from __future__ import annotations

from vnpy_ashare.domain.radar.leader import LeaderScoredRow
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.quotes.radar.radar_leader import leader_tier_label
from vnpy_ashare.quotes.radar.radar_models import RadarRow, apply_board_quality, merge_row_quotes


def row_from_leader_scored(scored: LeaderScoredRow) -> RadarRow | None:
    """龙头分层结果转雷达卡片行。"""
    row = merge_row_quotes(scored.row)
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    name = str(row.get("name") or (item.name if item else "") or vt_symbol)
    symbol = str(row.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    price_raw = row.get("last_price") or row.get("close")
    price = float(price_raw) if isinstance(price_raw, (int, float)) else None
    change_raw = row.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    tier_label = leader_tier_label(scored.leader_tier)
    axis_label = "概念" if scored.sector_axis == "concept" else "行业"
    sector_name = scored.sector_name or str(row.get("industry") or row.get("concept") or "—")
    return apply_board_quality(
        RadarRow(
            vt_symbol=vt_symbol,
            name=name,
            symbol=symbol,
            price=price,
            change_pct=change_pct,
            metric_label=tier_label or "龙头分",
            metric_value=f"{scored.leader_score:.0f}" if tier_label else f"{scored.leader_score:.0f}",
            sub_label=axis_label,
            sub_value=sector_name[:8],
            leader_score=scored.leader_score,
            leader_tier=scored.leader_tier,
            limit_times=scored.limit_times if scored.limit_times >= 1 else None,
        ),
        row,
    )


# 兼容旧私有名
_row_from_leader_scored = row_from_leader_scored
