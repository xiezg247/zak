"""个股板块、估值领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class ValuationProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    trade_date: str = Field(default="", description="交易日")
    pe_ttm: float | None = Field(default=None, description="市盈率 TTM")
    pb: float | None = Field(default=None, description="市净率")
    total_mv: float | None = Field(default=None, description="总市值（万元）")
    circ_mv: float | None = Field(default=None, description="流通市值（万元）")
    pe_percentile_3y: float | None = Field(default=None, description="PE 三年分位")
    pb_percentile_3y: float | None = Field(default=None, description="PB 三年分位")
    history_days: int = Field(default=0, description="历史样本天数")
    synced: bool = Field(default=False, description="是否已同步")
    message: str = Field(default="", description="说明信息")


class SectorProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(description="名称")
    industry: str = Field(default="", description="所属行业")
    trade_date: str = Field(default="", description="交易日")
    sector_count: int = Field(default=0, description="板块成分股数量")
    sector_avg_change_pct: float | None = Field(default=None, description="板块平均涨跌幅（%）")
    sector_rank: int | None = Field(default=None, description="板块内涨幅排名")
    peers: list[dict[str, Any]] = Field(default_factory=list, description="同行业对标股")
    disclosure: list[dict[str, str]] = Field(default_factory=list, description="披露计划")
