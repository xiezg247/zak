"""申万 2021 行业板块统一口径（L2 板块实体 + 东财资金流 overlay）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.integrations.tushare.sw_industry import (
    fetch_sw_l2_index_map,
)


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
    limit_each_side: int | None = 24,
) -> list[SectorFlowRow]:
    """东财行业 API 行 → 申万 L2 板块（仅保留申万名录内的行业）。

    limit_each_side=None 返回全量申万行业（用于摘要极值）；默认各侧 Top 24。
    """
    from vnpy_ashare.services.sector_flow import rows_from_dc_moneyflow, split_sector_display_rows

    raw = rows_from_dc_moneyflow(
        dc_rows,
        sector_kind=sector_kind,
        flow_source="dc_industry",
        top_each_side=None,
    )
    normalized = normalize_sw_industry_sector_rows([row.model_copy(update={"flow_source": flow_source}) for row in raw])
    if limit_each_side is None:
        return normalized
    inflow, outflow = split_sector_display_rows(normalized)
    return inflow[:limit_each_side] + outflow[:limit_each_side]


def overlay_dc_moneyflow_on_sw_rows(
    sw_rows: list[SectorFlowRow],
    dc_rows: list[dict[str, Any]],
) -> list[SectorFlowRow]:
    """盘中申万聚合榜叠加东财官方主力净额（按 L2 名匹配）。"""
    dc_by_name = {row.name: row for row in build_sw_industry_rows_from_dc(dc_rows, limit_each_side=None)}
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


# UI / 选股页 Tushare 行业门面（禁止 ui → integrations.tushare）
from vnpy_ashare.integrations.tushare.cache import get_cached_industry_map
from vnpy_ashare.integrations.tushare.factors import (
    fetch_industry_l2_to_l1_map,
    fetch_stock_industry_l1_map,
    fetch_stock_industry_map,
    fetch_stock_market_board_map,
)
from vnpy_ashare.integrations.tushare.index_amount import DEFAULT_TRADING_DAYS, fetch_index_amount_history
from vnpy_ashare.integrations.tushare.sw_industry import build_grouped_l2_industries, format_industry_filter_label

__all__ = [
    "DEFAULT_TRADING_DAYS",
    "build_grouped_l2_industries",
    "build_sw_industry_rows_from_dc",
    "fetch_index_amount_history",
    "fetch_industry_l2_to_l1_map",
    "fetch_stock_industry_l1_map",
    "fetch_stock_industry_map",
    "fetch_stock_market_board_map",
    "fetch_sw_l2_index_map",
    "format_industry_filter_label",
    "get_cached_industry_map",
    "normalize_sw_industry_sector_rows",
    "overlay_dc_moneyflow_on_sw_rows",
]


# UI / 选股页 Tushare 行业门面（禁止 ui → integrations.tushare）
from vnpy_ashare.integrations.tushare.cache import get_cached_industry_map
from vnpy_ashare.integrations.tushare.factors import (
    fetch_industry_l2_to_l1_map,
    fetch_stock_industry_l1_map,
    fetch_stock_industry_map,
    fetch_stock_market_board_map,
)
from vnpy_ashare.integrations.tushare.index_amount import DEFAULT_TRADING_DAYS, fetch_index_amount_history
from vnpy_ashare.integrations.tushare.sw_industry import build_grouped_l2_industries, format_industry_filter_label

__all__ = [
    "DEFAULT_TRADING_DAYS",
    "build_grouped_l2_industries",
    "build_sw_industry_rows_from_dc",
    "fetch_index_amount_history",
    "fetch_industry_l2_to_l1_map",
    "fetch_stock_industry_l1_map",
    "fetch_stock_industry_map",
    "fetch_stock_market_board_map",
    "fetch_sw_l2_index_map",
    "format_industry_filter_label",
    "get_cached_industry_map",
    "normalize_sw_industry_sector_rows",
    "overlay_dc_moneyflow_on_sw_rows",
]
