"""板块资金监控领域模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectorFlowRow:
    """单行业板块快照行。"""

    sector_id: str
    name: str
    strength: float
    change_pct: float
    net_flow_yi: float
    stock_count: int
    up_ratio: float
    flow_source: str  # proxy | tushare


@dataclass(frozen=True)
class SectorFlowSnapshot:
    rows: tuple[SectorFlowRow, ...]
    inflow_rows: tuple[SectorFlowRow, ...] = ()
    outflow_rows: tuple[SectorFlowRow, ...] = ()
    updated_at: str | None = ""
    trade_date: str = ""
    top_inflow_name: str = ""
    top_inflow_yi: float = 0.0
    top_outflow_name: str = ""
    top_outflow_yi: float = 0.0
    empty_hint: str = ""
