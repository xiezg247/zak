"""个股短线（打板 / 龙头）领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class ShortTermPeer(MutableModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(description="名称")
    leader_tier: str = Field(default="", description="龙头分层")
    leader_tier_label: str = Field(default="", description="龙头分层标签")
    limit_times: float = Field(default=0, description="连板数")
    change_pct: float | None = Field(default=None, description="涨跌幅（%）")


class ShortTermProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(default="", description="名称")
    trade_date: str = Field(default="", description="涨停列表交易日")
    limit_today: dict[str, Any] | None = Field(default=None, description="当日涨跌停档案")
    limit_times: float | None = Field(default=None, description="连板数")
    leader_tier: str = Field(default="", description="板块龙头分层")
    leader_tier_label: str = Field(default="", description="龙头分层标签")
    sector_name: str = Field(default="", description="所属行业")
    sector_rank: int = Field(default=0, description="行业内龙头排名")
    sector_peers: list[ShortTermPeer] = Field(default_factory=list, description="同板块龙头候选")
    entry_mode: dict[str, Any] = Field(default_factory=dict, description="买点模式评估")
    regulatory_summary: str = Field(default="", description="监管异动摘要")
    regulatory_risk_level: str = Field(default="none", description="监管风险等级")
    message: str = Field(default="", description="说明信息")
