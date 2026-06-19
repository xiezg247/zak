"""板块资金监控领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


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


class SectorFlowRotationRow(FrozenModel):
    """单板块近 N 日资金轮动行。"""

    sector: SectorFlowRow = Field(description="板块当日快照元数据")
    points: tuple[SectorFlowHistoryPoint, ...] = Field(description="按交易日升序的历史点")
    cumulative_net_yi: float = Field(description="窗口累计主力净流入（亿元）")
    positive_days: int = Field(description="净流入天数")
    flow_pattern: str = Field(description="流动方向标签")
    momentum_delta: float = Field(description="近5日累计 − 前10日累计（亿元）")
    rank_delta: int | None = Field(default=None, description="排名变化（正=排名上升）")


class SectorFlowRotationSnapshot(FrozenModel):
    """板块近 N 日轮动矩阵快照。"""

    trade_dates: tuple[str, ...] = Field(description="列头交易日（升序）")
    rows: tuple[SectorFlowRotationRow, ...] = Field(description="轮动行")
    sector_kind: str = Field(default="industry", description="行业或概念")
    updated_at: str = Field(default="", description="更新时间文案")
    empty_hint: str = Field(default="", description="无数据提示")
    data_mode: str = Field(default="official_dc", description="数据模式")


OUTLOOK_HORIZON_DAYS = 3
OUTLOOK_DISCLAIMER = "统计情景，非资金预测"


class SectorFlowOutlookDay(FrozenModel):
    """未来单日资金展望标签。"""

    trade_date: str = Field(description="交易日 YYYYMMDD")
    bias: str = Field(description="偏多/偏空/震荡")
    strength: float = Field(description="延续强度 0~1")


class SectorFlowOutlookRow(FrozenModel):
    """单板块未来 N 日展望行。"""

    sector: SectorFlowRow = Field(description="板块当日快照元数据")
    days: tuple[SectorFlowOutlookDay, ...] = Field(description="按 T+1~T+N 升序")
    headline_pattern: str = Field(description="延续模式或策略摘要")
    rationale: str = Field(description="规则说明")
    source: str = Field(description="continuation 或 strategy")


class SectorFlowOutlookSnapshot(FrozenModel):
    """板块未来 N 日展望快照。"""

    forward_dates: tuple[str, ...] = Field(description="T+1~T+N 列头")
    rows: tuple[SectorFlowOutlookRow, ...] = Field(description="展望行")
    sector_kind: str = Field(default="industry", description="行业或概念")
    source: str = Field(description="continuation 或 strategy")
    updated_at: str = Field(default="", description="更新时间文案")
    empty_hint: str = Field(default="", description="无数据提示")
    disclaimer: str = Field(default=OUTLOOK_DISCLAIMER, description="口径声明")
    data_mode: str = Field(default="official_dc", description="数据模式")


class SectorFlowOutlookCompareRow(FrozenModel):
    """A/B 对照行。"""

    sector: SectorFlowRow = Field(description="板块元数据")
    continuation: SectorFlowOutlookRow | None = Field(default=None, description="延续口径")
    strategy: SectorFlowOutlookRow | None = Field(default=None, description="策略口径")
    agreement: str = Field(description="一致/分歧/仅延续/仅策略")


class SectorFlowOutlookBundle(FrozenModel):
    """延续 + 策略 + 对照打包结果。"""

    continuation: SectorFlowOutlookSnapshot = Field(description="A 延续展望")
    strategy: SectorFlowOutlookSnapshot = Field(description="B 策略展望")
    compare_rows: tuple[SectorFlowOutlookCompareRow, ...] = Field(description="对照行")


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
