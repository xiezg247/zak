"""雷达页：板块·主线 loader。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar_models import RadarCardData, RadarRow, format_pct, merge_row_quotes
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.sector_strength import run_sector_strength
from vnpy_ashare.screener.sector.sector_summary import attach_industry, top_industries_by_momentum


def _sector_metric(row: dict[str, Any]) -> tuple[str, str, str, str]:
    merged = merge_row_quotes(row)
    industry = str(merged.get("industry") or "—")
    change = float(merged.get("change_pct") or 0)
    amount = float(merged.get("amount") or 0)
    if amount > 0:
        return "行业", industry[:8], "涨幅", format_pct(change)
    return "行业", industry[:8], "涨幅", format_pct(change)


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


def _build_leaders_rows(pool_size: int) -> tuple[list[RadarRow], str, int]:
    hits, total = run_sector_strength(pool_size, weight=1.0)
    rows: list[RadarRow] = []
    industries: list[str] = []
    for hit in hits:
        parsed = _row_from_sector_hit(hit.row)
        if parsed is None:
            continue
        rows.append(parsed)
        industry = str(hit.row.get("industry") or "")
        if industry and industry not in industries:
            industries.append(industry)
    subtitle = ""
    if industries:
        subtitle = "主线：" + "、".join(industries[:3])
    if total:
        subtitle = (subtitle + " · " if subtitle else "") + f"扫描 {total} 只"
    return rows, subtitle, total


def _build_breadth_rows(pool_size: int) -> tuple[list[RadarRow], str, int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], "", 0

    enriched = attach_industry(snapshot.rows)
    if not enriched:
        return [], "", snapshot.total

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        industry = str(row.get("industry") or "").strip()
        if industry:
            buckets[industry].append(row)

    industry_stats: list[tuple[str, float, float, list[dict[str, Any]]]] = []
    for industry, items in buckets.items():
        if len(items) < 3:
            continue
        positive = sum(1 for item in items if float(item.get("change_pct") or 0) > 0)
        ratio = positive / len(items)
        avg_change = sum(float(item.get("change_pct") or 0) for item in items) / len(items)
        industry_stats.append((industry, ratio, avg_change, items))

    industry_stats.sort(key=lambda item: (item[1], item[2], len(item[3])), reverse=True)
    strong = industry_stats[:5]
    if not strong:
        return [], "", snapshot.total

    candidates: list[dict[str, Any]] = []
    for _industry, ratio, avg_change, items in strong:
        ranked = sorted(items, key=lambda item: float(item.get("change_pct") or 0), reverse=True)
        for item in ranked[: max(2, pool_size // 5)]:
            merged = dict(item)
            merged["breadth_ratio"] = round(ratio * 100, 1)
            merged["industry_avg_change"] = round(avg_change, 2)
            candidates.append(merged)

    candidates.sort(
        key=lambda item: (
            float(item.get("breadth_ratio") or 0),
            float(item.get("change_pct") or 0),
        ),
        reverse=True,
    )

    rows: list[RadarRow] = []
    for row in candidates[:pool_size]:
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

    leaders = top_industries_by_momentum(enriched, top_industry_count=3)
    subtitle = ""
    if leaders:
        subtitle = "扩散：" + "、".join(leaders)
    subtitle = (subtitle + " · " if subtitle else "") + f"扫描 {snapshot.total} 只"
    return rows, subtitle, snapshot.total


def load_sector_theme(spec: RadarCardSpec, *, variant: str = "leaders") -> RadarCardData:
    if variant == "breadth":
        rows, subtitle, total = _build_breadth_rows(spec.top_n)
        empty = "暂无板块广度数据，请先同步行业信息或采集行情。"
    else:
        rows, subtitle, total = _build_leaders_rows(spec.top_n)
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
        )

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle or f"Top {len(rows)}",
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(rows),
    )
