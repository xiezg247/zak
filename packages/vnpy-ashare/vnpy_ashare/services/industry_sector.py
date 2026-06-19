"""申万 2021 行业板块统一口径（L2 板块实体 + 东财资金流 overlay）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.integrations.tushare.sw_industry import fetch_sw_l2_index_map


def normalize_sw_industry_sector_rows(rows: list[SectorFlowRow]) -> list[SectorFlowRow]:
    """将行业板块行统一为申万 L2 index_code；非申万行业名丢弃。"""
    l2_index = fetch_sw_l2_index_map()
    if not l2_index:
        return rows

    normalized: list[SectorFlowRow] = []
    for row in rows:
        if row.sector_kind != "industry":
            normalized.append(row)
            continue
        name = str(row.name or "").strip()
        index_code = l2_index.get(name)
        if not index_code:
            continue
        flow_source = str(row.flow_source or "").strip()
        if flow_source == "dc_industry":
            flow_source = "sw_dc"
        normalized.append(
            row.model_copy(
                update={
                    "sector_id": index_code,
                    "flow_source": flow_source or "sw",
                }
            )
        )
    return normalized


def build_sw_industry_rows_from_dc(
    dc_rows: list[dict[str, Any]],
    *,
    sector_kind: str = "industry",
    flow_source: str = "sw_dc",
    top_each_side: int | None = None,
) -> list[SectorFlowRow]:
    """东财行业 API 行 → 申万 L2 板块（仅保留申万名录内的行业）。"""
    from vnpy_ashare.services.sector_flow import rows_from_dc_moneyflow

    raw = rows_from_dc_moneyflow(
        dc_rows,
        sector_kind=sector_kind,
        flow_source="dc_industry",
        top_each_side=top_each_side,
    )
    return normalize_sw_industry_sector_rows(
        [row.model_copy(update={"flow_source": flow_source}) for row in raw]
    )


def overlay_dc_moneyflow_on_sw_rows(
    sw_rows: list[SectorFlowRow],
    dc_rows: list[dict[str, Any]],
) -> list[SectorFlowRow]:
    """盘中申万聚合榜叠加东财官方主力净额（按 L2 名匹配）。"""
    dc_by_name = {row.name: row for row in build_sw_industry_rows_from_dc(dc_rows, top_each_side=None)}
    if not dc_by_name:
        return sw_rows

    merged: list[SectorFlowRow] = []
    for row in sw_rows:
        dc = dc_by_name.get(row.name)
        if dc is None:
            merged.append(row)
            continue
        merged.append(
            row.model_copy(
                update={
                    "net_flow_yi": dc.net_flow_yi,
                    "net_flow_rate": dc.net_flow_rate,
                    "leader_stock": dc.leader_stock or row.leader_stock,
                    "change_pct": dc.change_pct if dc.change_pct else row.change_pct,
                    "flow_source": "sw_dc",
                }
            )
        )
    return merged
