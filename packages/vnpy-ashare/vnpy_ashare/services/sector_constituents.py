"""板块成分龙头解析。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.sector_flow import SectorConstituentRow, SectorFlowRow
from vnpy_ashare.integrations.tushare.concept_board import (
    fetch_ths_concept_index_map,
    fetch_ths_member_vt_symbols,
)
from vnpy_ashare.screener.sector.sector_summary import attach_industry


def _row_to_constituent(row: dict[str, Any]) -> SectorConstituentRow | None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    name = str(row.get("name") or vt_symbol.split(".")[0]).strip()
    change_pct = float(row.get("change_pct") or 0)
    net_mf_wan = float(row.get("net_mf_amount") or 0)
    return SectorConstituentRow(
        vt_symbol=vt_symbol,
        name=name,
        change_pct=round(change_pct, 2),
        net_mf_wan=round(net_mf_wan, 2),
    )


def _resolve_concept_vt_symbols(sector: SectorFlowRow) -> set[str]:
    sector_id = str(sector.sector_id or "").strip()
    if sector_id.endswith(".TI"):
        return set(fetch_ths_member_vt_symbols(sector_id))
    concept_map = fetch_ths_concept_index_map()
    for code, name in concept_map.items():
        if name == sector.name:
            return set(fetch_ths_member_vt_symbols(code))
    return set()


def _filter_industry_rows(
    quote_rows: list[dict[str, Any]],
    industry: str,
    *,
    industry_map: dict[str, str] | None,
) -> list[dict[str, Any]]:
    enriched = attach_industry(quote_rows, industry_map=industry_map)
    return [row for row in enriched if str(row.get("industry") or "").strip() == industry]


def resolve_concept_vt_symbols(sector: SectorFlowRow) -> set[str]:
    return _resolve_concept_vt_symbols(sector)


def load_sector_leaders(
    sector: SectorFlowRow,
    quote_rows: list[dict[str, Any]],
    *,
    industry_map: dict[str, str] | None = None,
    limit: int = 5,
) -> list[SectorConstituentRow]:
    """按涨幅/主力排序返回板块成分龙头。"""
    if sector.sector_kind == "concept":
        vt_symbols = _resolve_concept_vt_symbols(sector)
        if vt_symbols:
            matched = [row for row in quote_rows if str(row.get("vt_symbol") or "") in vt_symbols]
        else:
            matched = []
    else:
        matched = _filter_industry_rows(quote_rows, sector.name, industry_map=industry_map)

    leaders: list[SectorConstituentRow] = []
    ranked = sorted(
        matched,
        key=lambda item: (
            float(item.get("change_pct") or 0),
            float(item.get("net_mf_amount") or 0),
        ),
        reverse=True,
    )
    for row in ranked:
        parsed = _row_to_constituent(row)
        if parsed is None:
            continue
        leaders.append(parsed)
        if len(leaders) >= limit:
            break

    if leaders:
        return leaders

    if sector.leader_stock:
        return [
            SectorConstituentRow(
                vt_symbol="",
                name=sector.leader_stock,
                change_pct=sector.change_pct,
                net_mf_wan=0.0,
            )
        ]
    return []


def compute_divergence_rows(
    rows: list[SectorFlowRow],
    *,
    min_change_pct: float = 0.3,
    min_flow_yi: float = 0.3,
    top_n: int = 24,
) -> list[SectorFlowRow]:
    """量价背离：价涨流出 / 价跌流入。"""
    hits: list[SectorFlowRow] = []
    for row in rows:
        if row.change_pct >= min_change_pct and row.net_flow_yi <= -min_flow_yi:
            hits.append(row.model_copy(update={"divergence_kind": "价涨流出"}))
        elif row.change_pct <= -min_change_pct and row.net_flow_yi >= min_flow_yi:
            hits.append(row.model_copy(update={"divergence_kind": "价跌流入"}))
    hits.sort(
        key=lambda item: abs(item.change_pct) + abs(item.net_flow_yi),
        reverse=True,
    )
    return hits[:top_n]
