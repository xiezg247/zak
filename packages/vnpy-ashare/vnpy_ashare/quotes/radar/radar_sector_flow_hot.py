"""板块·资金热度 loader（行业/概念主力净流入 Top）。"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_map
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.sector.sector_summary import attach_industry, attach_sector_fields
from vnpy_ashare.services.sector_flow import aggregate_sector_rows, format_sector_net_flow_yi

SectorFlowHotVariant = Literal["industry", "concept"]

_MIN_STOCKS = 3


def _leader_row_for_sector(
    sector_name: str,
    items: list[dict],
    *,
    axis_label: str,
    net_flow_yi: float,
) -> RadarRow | None:
    if not items:
        return None
    leader = max(items, key=lambda item: float(item.get("change_pct") or 0))
    merged = merge_row_quotes(leader)
    vt_symbol = str(merged.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    name = str(merged.get("name") or (item.name if item else "") or vt_symbol)
    symbol = str(merged.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    price_raw = merged.get("last_price") or merged.get("close")
    price = float(price_raw) if isinstance(price_raw, (int, float)) else None
    change_raw = merged.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        metric_label="净流入",
        metric_value=format_sector_net_flow_yi(net_flow_yi),
        sub_label=axis_label,
        sub_value=sector_name[:8],
    )


def _aggregate_concept_sectors(rows: list) -> list[tuple[SectorFlowRow, list[dict]]]:
    enriched, _hot = attach_sector_fields(rows)
    pool = enriched or rows
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in pool:
        concept = str(row.get("concept") or "").strip()
        if not concept:
            continue
        buckets[concept].append(dict(row))

    result: list[tuple[SectorFlowRow, list[dict]]] = []
    for concept, items in buckets.items():
        if len(items) < _MIN_STOCKS:
            continue
        changes = [float(item.get("change_pct") or 0) for item in items]
        avg_change = sum(changes) / len(changes)
        up_count = sum(1 for value in changes if value > 0)
        up_ratio = up_count / len(items)
        net_yi = sum(float(item.get("net_mf_amount") or 0) for item in items) / 10000.0
        if net_yi == 0:
            from vnpy_ashare.services.sector_flow import _proxy_flow_yi

            net_yi = sum(_proxy_flow_yi(item) for item in items)
        sector = SectorFlowRow(
            sector_id=concept,
            name=concept,
            strength=round(up_ratio * 100 + avg_change, 2),
            change_pct=round(avg_change, 2),
            net_flow_yi=round(net_yi, 2),
            stock_count=len(items),
            up_ratio=round(up_ratio, 4),
            flow_source="proxy",
            sector_kind="concept",
        )
        result.append((sector, items))
    result.sort(key=lambda item: item[0].net_flow_yi, reverse=True)
    return result


def load_sector_flow_hot(spec: RadarCardSpec, *, variant: SectorFlowHotVariant = "industry") -> RadarCardData:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message="暂无行情数据，请先采集行情。",
            updated_at=format_china_datetime_minute(),
        )

    axis_label = "概念" if variant == "concept" else "行业"
    sector_names: list[str] = []
    rows: list[RadarRow] = []

    if variant == "concept":
        aggregated = _aggregate_concept_sectors(list(snapshot.rows))
        hot_sectors = [item for item in aggregated if item[0].net_flow_yi > 0][: spec.top_n]
        for sector, items in hot_sectors:
            row = _leader_row_for_sector(sector.name, items, axis_label=axis_label, net_flow_yi=sector.net_flow_yi)
            if row is None:
                continue
            rows.append(row)
            sector_names.append(sector.name)
    else:
        industry_map = fetch_stock_industry_map()
        enriched = attach_industry(list(snapshot.rows), industry_map=industry_map)
        sector_rows = aggregate_sector_rows(enriched or list(snapshot.rows), industry_map=industry_map)
        inflow = [sector for sector in sector_rows if sector.net_flow_yi > 0][: spec.top_n]

        by_industry: dict[str, list[dict]] = defaultdict(list)
        for row in enriched or snapshot.rows:
            industry = str(row.get("industry") or "").strip()
            if industry:
                by_industry[industry].append(dict(row))

        for sector in inflow:
            items = by_industry.get(sector.name, [])
            row = _leader_row_for_sector(sector.name, items, axis_label=axis_label, net_flow_yi=sector.net_flow_yi)
            if row is None:
                continue
            rows.append(row)
            sector_names.append(sector.name)

    if not rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {snapshot.total} 只",
            rows=(),
            empty_message=f"暂无{axis_label}主力净流入板块。",
            updated_at=format_china_datetime_minute(),
            total_count=int(snapshot.total or 0),
        )

    top_flow = rows[0].metric_value if rows else "—"
    subtitle = f"{axis_label}净流入 Top {len(rows)} · 榜首 {top_flow} · 扫描 {snapshot.total} 只"

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at=format_china_datetime_minute(),
        total_count=len(rows),
        sector_names=tuple(sector_names),
    )
