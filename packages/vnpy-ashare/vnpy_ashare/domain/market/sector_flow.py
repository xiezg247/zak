"""板块资金监控领域模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectorFlowRow:
    """单行业/概念板块快照行。"""

    sector_id: str
    name: str
    strength: float
    change_pct: float
    net_flow_yi: float
    stock_count: int
    up_ratio: float
    flow_source: str  # proxy | tushare | dc_industry | dc_concept | ths_concept
    sector_kind: str = "industry"  # industry | concept
    leader_stock: str = ""
    net_flow_rate: float = 0.0
    divergence_kind: str = ""  # 价涨流出 | 价跌流入


@dataclass(frozen=True)
class SectorConstituentRow:
    """板块成分龙头行。"""

    vt_symbol: str
    name: str
    change_pct: float
    net_mf_wan: float


@dataclass(frozen=True)
class SectorFlowHistoryPoint:
    """板块日终主力净流入历史点。"""

    trade_date: str
    net_flow_yi: float


@dataclass(frozen=True)
class SectorFlowSnapshot:
    rows: tuple[SectorFlowRow, ...]
    inflow_rows: tuple[SectorFlowRow, ...] = ()
    outflow_rows: tuple[SectorFlowRow, ...] = ()
    divergence_rows: tuple[SectorFlowRow, ...] = ()
    updated_at: str | None = ""
    trade_date: str = ""
    top_inflow_name: str = ""
    top_inflow_yi: float = 0.0
    top_outflow_name: str = ""
    top_outflow_yi: float = 0.0
    empty_hint: str = ""
    sector_kind: str = "industry"
    data_mode: str = "intraday"  # intraday | official_dc | official_ths
