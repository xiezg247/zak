"""个股诊断与资金流领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class DiagnoseMetrics(MutableModel):
    macd: float | None = Field(default=None, description="MACD 值")
    dif: float | None = Field(default=None, description="DIF 值")
    dea: float | None = Field(default=None, description="DEA 值")
    kdj_k: float | None = Field(default=None, description="KDJ K 值")
    kdj_d: float | None = Field(default=None, description="KDJ D 值")
    kdj_j: float | None = Field(default=None, description="KDJ J 值")
    rsi: float | None = Field(default=None, description="RSI 值")
    pe_ttm: float | None = Field(default=None, description="市盈率 TTM")
    roe: float | None = Field(default=None, description="净资产收益率")
    main_net: float | None = Field(default=None, description="主力净流入")
    industry: str = Field(default="", description="所属行业")
    source: str = Field(default="tdx_mcp", description="数据来源")


class MoneyflowDayRow(MutableModel):
    trade_date: str = Field(description="交易日")
    net_mf_amount: float | None = Field(default=None, description="主力净流入（万元）")
    buy_elg_amount: float | None = Field(default=None, description="特大单买入金额")
    sell_elg_amount: float | None = Field(default=None, description="特大单卖出金额")


class MoneyflowProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    latest: MoneyflowDayRow | None = Field(default=None, description="最新一日资金流")
    history: list[MoneyflowDayRow] = Field(default_factory=list, description="历史资金流")
    message: str = Field(default="", description="说明信息")
