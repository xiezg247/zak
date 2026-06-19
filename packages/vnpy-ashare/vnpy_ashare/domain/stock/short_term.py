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


class LimitHistoryRow(MutableModel):
    trade_date: str = Field(description="交易日")
    limit_times: float | None = Field(default=None, description="连板数")
    first_time: str = Field(default="", description="首封时间")
    last_time: str = Field(default="", description="末封时间")
    fd_amount: float | None = Field(default=None, description="封单金额")
    open_times: int | None = Field(default=None, description="开板次数")
    strth: float | None = Field(default=None, description="封板强度（Tushare）")


class LimitStats(MutableModel):
    lookback_days: int = Field(default=20, description="统计窗口（交易日）")
    limit_up_days: int = Field(default=0, description="涨停天数")
    open_board_days: int = Field(default=0, description="开板天数")
    solid_seal_days: int = Field(default=0, description="一字/未开板天数")


class TopListRow(MutableModel):
    trade_date: str = Field(description="交易日")
    close: float | None = Field(default=None, description="收盘价")
    pct_change: float | None = Field(default=None, description="涨跌幅（%）")
    turnover_rate: float | None = Field(default=None, description="换手率（%）")
    net_amount: float | None = Field(default=None, description="龙虎榜净买额")
    net_rate: float | None = Field(default=None, description="净买占比（%）")
    reason: str = Field(default="", description="上榜理由")


class TopInstRow(MutableModel):
    exalter: str = Field(description="营业部")
    buy: float | None = Field(default=None, description="买入额")
    sell: float | None = Field(default=None, description="卖出额")
    net_buy: float | None = Field(default=None, description="净买额")


class ShortTermProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(default="", description="名称")
    trade_date: str = Field(default="", description="涨停列表交易日")
    limit_today: dict[str, Any] | None = Field(default=None, description="当日涨跌停档案")
    limit_times: float | None = Field(default=None, description="连板数")
    seal_strength: float | None = Field(default=None, description="封板强度 0–1")
    seal_strength_label: str = Field(default="", description="封板强度标签")
    seal_reopen_label: str = Field(default="", description="封板状态")
    limit_history: list[LimitHistoryRow] = Field(default_factory=list, description="近 N 日涨停史")
    limit_stats: LimitStats | None = Field(default=None, description="涨停统计")
    leader_tier: str = Field(default="", description="板块龙头分层")
    leader_tier_label: str = Field(default="", description="龙头分层标签")
    sector_name: str = Field(default="", description="所属行业")
    sector_rank: int = Field(default=0, description="行业内龙头排名")
    sector_peers: list[ShortTermPeer] = Field(default_factory=list, description="同板块龙头候选")
    entry_mode: dict[str, Any] = Field(default_factory=dict, description="买点模式评估")
    top_list: list[TopListRow] = Field(default_factory=list, description="龙虎榜历史上榜")
    top_inst_buy: list[TopInstRow] = Field(default_factory=list, description="最近上榜买入前五")
    top_inst_sell: list[TopInstRow] = Field(default_factory=list, description="最近上榜卖出前五")
    top_inst_date: str = Field(default="", description="机构席位数据日期")
    regulatory_summary: str = Field(default="", description="监管异动摘要")
    regulatory_risk_level: str = Field(default="none", description="监管风险等级")
    message: str = Field(default="", description="说明信息")
