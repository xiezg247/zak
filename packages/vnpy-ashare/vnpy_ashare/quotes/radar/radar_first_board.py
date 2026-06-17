"""发现·首板人气 loader。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_leader import _seal_quality_proxy
from vnpy_ashare.quotes.radar.radar_limit_ladder import (
    build_limit_ladder_candidates,
    resolve_limit_times,
)
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.screener.data.data_source import fetch_limit_list_with_fallback, load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.sector_strength import run_sector_strength
from vnpy_ashare.screener.sector.sector_summary import attach_industry

_STRONG_INDUSTRY_TOP = 5


def _parse_clock_minutes(text: str) -> int | None:
    raw = str(text or "").strip().replace(":", "")
    if len(raw) < 4:
        return None
    try:
        hours = int(raw[:2])
        minutes = int(raw[2:4])
    except ValueError:
        return None
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        return None
    return hours * 60 + minutes


def seal_time_score(first_time: str) -> float:
    """封板时间得分；缺失时返回 0。"""
    minutes = _parse_clock_minutes(first_time)
    if minutes is None:
        return 0.0
    if 565 <= minutes <= 630:
        return 1.0
    if 630 < minutes <= 810:
        return 0.7
    if 810 < minutes <= 900:
        return 0.5
    return 0.0


def format_seal_time_label(first_time: str) -> str:
    minutes = _parse_clock_minutes(first_time)
    if minutes is None:
        return ""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d} 封板"


def load_limit_list_first_time_map() -> dict[str, str]:
    """vt_symbol → first_time（Tushare limit_list_d，缺失则空）。"""
    rows, _ = fetch_limit_list_with_fallback(limit_type="U")
    result: dict[str, str] = {}
    for row in rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            continue
        first_time = str(row.get("first_time") or "").strip()
        if first_time:
            result[vt_symbol] = first_time
    return result


def _amount_rank_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    amounts = [(str(row.get("vt_symbol") or ""), float(row.get("amount") or 0)) for row in rows]
    amounts = [(vt, amt) for vt, amt in amounts if vt]
    if not amounts:
        return {}
    sorted_amounts = sorted(amount for _, amount in amounts)
    n = len(sorted_amounts)
    result: dict[str, float] = {}
    for vt, amount in amounts:
        if amount <= 0:
            result[vt] = 0.0
            continue
        rank = sum(1 for value in sorted_amounts if value <= amount)
        result[vt] = rank / n
    return result


def _strong_industries() -> set[str]:
    hits, _total = run_sector_strength(_STRONG_INDUSTRY_TOP * 4, weight=1.0)
    industries: list[str] = []
    for hit in hits:
        industry = str(hit.row.get("industry") or "").strip()
        if industry and industry not in industries:
            industries.append(industry)
        if len(industries) >= _STRONG_INDUSTRY_TOP:
            break
    return set(industries)


def build_first_board_candidates(
    rows: list[dict[str, Any]],
    *,
    limit_times_map: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """当日首板池：limit_times == 1。"""
    limit_up = build_limit_ladder_candidates(rows, limit_times_map=limit_times_map)
    return [row for row in limit_up if resolve_limit_times(row, limit_times_map=limit_times_map) == 1]


def compute_first_board_score(
    row: dict[str, Any],
    *,
    amount_rank: float,
    sector_bonus: float,
    seal_score: float,
) -> float:
    seal_quality = _seal_quality_proxy(row)
    if seal_score <= 0:
        seal_score = seal_quality * 0.6
    parts = {
        "seal_time": min(1.0, max(0.0, seal_score)),
        "amount": min(1.0, max(0.0, amount_rank)),
        "seal_quality": seal_quality,
        "sector": 1.0 if sector_bonus > 0 else 0.0,
    }
    weights = {"seal_time": 0.45, "amount": 0.30, "seal_quality": 0.15, "sector": 0.10}
    score = sum(parts[key] * weights[key] for key in weights) * 100.0
    return round(max(0.0, min(100.0, score)), 1)


def rank_first_board_pool(
    candidates: list[dict[str, Any]],
    *,
    first_time_map: dict[str, str] | None = None,
    top_n: int = 8,
) -> list[tuple[dict[str, Any], float, str]]:
    if not candidates:
        return []
    time_map = first_time_map or {}
    amount_ranks = _amount_rank_map(candidates)
    strong = _strong_industries()
    scored: list[tuple[dict[str, Any], float, str]] = []
    for row in candidates:
        vt = str(row.get("vt_symbol") or "")
        industry = str(row.get("industry") or "").strip()
        first_time = time_map.get(vt, "")
        seal_score = seal_time_score(first_time)
        popularity = compute_first_board_score(
            row,
            amount_rank=amount_ranks.get(vt, 0.0),
            sector_bonus=1.0 if industry in strong else 0.0,
            seal_score=seal_score,
        )
        scored.append((row, popularity, format_seal_time_label(first_time)))
    scored.sort(key=lambda item: (item[1], float(item[0].get("amount") or 0)), reverse=True)
    return scored[:top_n]


def _row_to_radar(row: dict[str, Any], *, popularity: float, seal_label: str) -> RadarRow | None:
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
    seal_text = seal_label or "—"
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        metric_label="封板",
        metric_value=seal_text,
        sub_label="人气",
        sub_value=f"{popularity:.0f}",
        limit_times=1.0,
    )


def load_first_board(spec: RadarCardSpec) -> RadarCardData:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message="暂无行情数据，请先采集行情或打开「市场」页。",
            updated_at="",
        )

    from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map

    enriched = attach_industry(snapshot.rows)
    limit_map = get_cached_limit_times_map()
    candidates = build_first_board_candidates(enriched, limit_times_map=limit_map)
    first_time_map = load_limit_list_first_time_map()

    if not candidates:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {snapshot.total} 只 · 首板 0",
            rows=(),
            empty_message="暂无首板标的，请同步行情或等待盘中涨停数据。",
            updated_at="",
            total_count=snapshot.total,
        )

    ranked = rank_first_board_pool(
        candidates,
        first_time_map=first_time_map,
        top_n=spec.top_n,
    )
    rows: list[RadarRow] = []
    for row, popularity, seal_label in ranked:
        parsed = _row_to_radar(row, popularity=popularity, seal_label=seal_label)
        if parsed is not None:
            rows.append(parsed)

    has_seal = sum(1 for _row, _score, label in ranked if label)
    subtitle = f"首板 {len(candidates)} · 展示 {len(rows)}"
    if has_seal:
        subtitle += f" · 封板时间 {has_seal}"
    subtitle += f" · 扫描 {snapshot.total} 只"

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(candidates),
    )
