"""板块资金监控领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel


class SectorFlowRow(FrozenModel):
    """单行业/概念板块快照行。"""

    sector_id: str = Field(description="板块唯一标识")
    name: str = Field(description="板块名称")
    strength: float = Field(description="板块强度得分")
    change_pct: float = Field(description="板块涨跌幅（%）")
    net_flow_yi: float = Field(description="主力净流入（亿元）")
    stock_count: int = Field(description="成分股数量")
    up_ratio: float = Field(description="上涨家数占比（0-1）")
    flow_source: str = Field(description="资金流数据来源（proxy/tushare/dc_industry 等）")
    sector_kind: str = Field(default="industry", description="板块类型：industry 或 concept")
    leader_stock: str = Field(default="", description="领涨股展示名")
    net_flow_rate: float = Field(default=0.0, description="净流入占成交额比率")
    divergence_kind: str = Field(default="", description="价量背离类型（价涨流出/价跌流入）")


class SectorConstituentRow(FrozenModel):
    """板块成分龙头行。"""

    vt_symbol: str = Field(description="VeighNa 合约代码")
    name: str = Field(description="证券简称")
    change_pct: float = Field(description="涨跌幅（%）")
    net_mf_wan: float = Field(description="主力净流入（万元）")


class SectorFlowHistoryPoint(FrozenModel):
    """板块日终主力净流入历史点。"""

    trade_date: str = Field(description="交易日 YYYY-MM-DD")
    net_flow_yi: float = Field(description="主力净流入（亿元）")


class SectorFlowSnapshot(FrozenModel):
    rows: tuple[SectorFlowRow, ...] = Field(description="全量板块行")
    inflow_rows: tuple[SectorFlowRow, ...] = Field(default=(), description="净流入 Top 板块")
    outflow_rows: tuple[SectorFlowRow, ...] = Field(default=(), description="净流出 Top 板块")
    divergence_rows: tuple[SectorFlowRow, ...] = Field(default=(), description="价量背离板块")
    updated_at: str | None = Field(default="", description="快照更新时间")
    trade_date: str = Field(default="", description="对应交易日")
    top_inflow_name: str = Field(default="", description="最大净流入板块名")
    top_inflow_yi: float = Field(default=0.0, description="最大净流入金额（亿元）")
    top_outflow_name: str = Field(default="", description="最大净流出板块名")
    top_outflow_yi: float = Field(default=0.0, description="最大净流出金额（亿元）")
    empty_hint: str = Field(default="", description="无数据时的提示文案")
    sector_kind: str = Field(default="industry", description="当前快照板块类型")
    data_mode: str = Field(default="intraday", description="数据模式：intraday/official_dc/official_ths")
