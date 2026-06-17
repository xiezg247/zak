"""板块·主线 loader（含 leader_score 分层）。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_leader import LeaderScoredRow, leader_tier_label, rank_unified_sector_leaders
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, format_pct, merge_row_quotes
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.sector_strength import run_sector_strength
from vnpy_ashare.screener.sector.sector_summary import (
    attach_industry,
    attach_sector_fields,
    breadth_leader_candidates,
    compute_sector_distribution,
    top_industries_by_breadth,
)
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields


def _sector_metric(row: dict[str, Any]) -> tuple[str, str, str, str]:
    merged = merge_row_quotes(row)
    industry = str(merged.get("industry") or "—")
    change = float(merged.get("change_pct") or 0)
    amount = float(merged.get("amount") or 0)
    if amount > 0:
        return "行业", industry[:8], "涨幅", format_pct(change)
    return "行业", industry[:8], "涨幅", format_pct(change)


def _row_from_leader_scored(scored: LeaderScoredRow) -> RadarRow | None:
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
    return RadarRow(
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
    )


def _row_from_sector_hit(row: dict[str, Any]) -> RadarRow | None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    merged = merge_row_quotes(row)
    name = str(merged.get("name") or (item.name if item else "") or vt_symbol)
    symbol = str(merged.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    price_raw = merged.get("last_price") or merged.get("close")
    price = float(price_raw) if isinstance(price_raw, (int, float)) else None
    change_raw = merged.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    metric_label, metric_value, sub_label, sub_value = _sector_metric(merged)
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def _build_leaders_rows(pool_size: int) -> tuple[list[RadarRow], str, int, tuple[str, ...]]:
    """兼容旧 variant=leaders：与 leaders_tiered 相同。"""
    return _build_leaders_tiered_rows(pool_size)


def _build_leaders_tiered_rows(pool_size: int) -> tuple[list[RadarRow], str, int, tuple[str, ...]]:
    hits, total = run_sector_strength(max(pool_size * 4, 40), weight=1.0)
    candidates = [dict(hit.row) for hit in hits]
    enriched, hot_concepts = attach_sector_fields(candidates)
    if enriched:
        candidates = enriched
    attach_first_time_fields(candidates)
    industry_distribution = compute_sector_distribution(enriched or candidates, top_n=8, min_stocks=3)
    strong_industries = {str(item["industry"]) for item in industry_distribution[:5]}
    strong_concepts = set(hot_concepts)
    ranked = rank_unified_sector_leaders(
        candidates,
        max_per_sector=5,
        strong_industries=strong_industries,
        strong_concepts=strong_concepts,
    )

    by_sector: dict[str, list[LeaderScoredRow]] = defaultdict(list)
    sector_order: list[str] = []
    for scored in ranked:
        sector = scored.sector_name or str(scored.row.get("industry") or scored.row.get("concept") or "—")
        if sector not in by_sector:
            sector_order.append(sector)
        by_sector[sector].append(scored)

    tier_limits = {"dragon_1": 1, "dragon_2": 1, "follower": 1}
    rows: list[RadarRow] = []
    tier_parts: list[str] = []
    for sector in sector_order:
        tier_counts: dict[str, int] = defaultdict(int)
        sector_added = 0
        for scored in by_sector[sector]:
            tier = scored.leader_tier or "follower"
            limit = tier_limits.get(tier, 0)
            if limit and tier_counts[tier] >= limit:
                continue
            if tier in tier_limits:
                tier_counts[tier] += 1
            parsed = _row_from_leader_scored(scored)
            if parsed is None:
                continue
            rows.append(parsed)
            sector_added += 1
            if len(rows) >= pool_size:
                break
        if sector_added:
            dragons = tier_counts.get("dragon_1", 0) + tier_counts.get("dragon_2", 0)
            tier_parts.append(f"{sector}×{dragons or sector_added}")
        if len(rows) >= pool_size:
            break

    subtitle = ""
    if tier_parts:
        subtitle = "分层：" + "、".join(tier_parts[:4])
    if hot_concepts:
        subtitle = (subtitle + " · " if subtitle else "") + "概念：" + "、".join(hot_concepts[:2])
    if total:
        subtitle = (subtitle + " · " if subtitle else "") + f"扫描 {total} 只"
    if rows:
        subtitle = (subtitle + " · " if subtitle else "") + "龙一/龙二/跟风"
    return rows, subtitle, total, tuple(sector_order[:6])


def _build_breadth_rows(pool_size: int) -> tuple[list[RadarRow], str, int, tuple[str, ...]]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], "", 0, ()

    enriched = attach_industry(snapshot.rows)
    if not enriched:
        return [], "", snapshot.total, ()

    candidates = breadth_leader_candidates(enriched, pool_size=pool_size)
    if not candidates:
        return [], "", snapshot.total, ()

    rows: list[RadarRow] = []
    for row in candidates:
        parsed = _row_from_sector_hit(row)
        if parsed is None:
            continue
        breadth = float(row.get("breadth_ratio") or 0)
        rows.append(
            RadarRow(
                vt_symbol=parsed.vt_symbol,
                name=parsed.name,
                symbol=parsed.symbol,
                price=parsed.price,
                change_pct=parsed.change_pct,
                metric_label="上涨占比",
                metric_value=f"{breadth:.0f}%",
                sub_label=parsed.sub_label,
                sub_value=parsed.sub_value,
            )
        )

    leaders = top_industries_by_breadth(enriched, top_industry_count=6)
    subtitle = ""
    if leaders:
        subtitle = "扩散：" + "、".join(str(item.get("industry") or "") for item in leaders[:3])
    subtitle = (subtitle + " · " if subtitle else "") + f"扫描 {snapshot.total} 只"
    return rows, subtitle, snapshot.total, tuple(str(item.get("industry") or "") for item in leaders[:6])


def load_sector_theme(spec: RadarCardSpec, *, variant: str = "leaders_tiered") -> RadarCardData:
    if variant == "breadth":
        rows, subtitle, total, sector_names = _build_breadth_rows(spec.top_n)
        empty = "暂无板块广度数据，请先同步行业信息或采集行情。"
    elif variant in {"leaders", "leaders_tiered"}:
        rows, subtitle, total, sector_names = _build_leaders_tiered_rows(spec.top_n)
        empty = "暂无板块主线数据，请先同步行业信息或采集行情。"
    else:
        rows, subtitle, total, sector_names = _build_leaders_tiered_rows(spec.top_n)
        empty = "暂无板块主线数据，请先同步行业信息或采集行情。"

    if not rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=subtitle,
            rows=(),
            empty_message=empty,
            updated_at="",
            total_count=total,
            sector_names=sector_names,
        )

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle or f"Top {len(rows)}",
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(rows),
        sector_names=sector_names,
    )
