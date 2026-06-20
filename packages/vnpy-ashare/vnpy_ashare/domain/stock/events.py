"""个股事件日历领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class EventsProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    disclosure: list[dict[str, str]] = Field(default_factory=list, description="披露计划")
    dividends: list[dict[str, Any]] = Field(default_factory=list, description="分红记录")
    share_float: list[dict[str, Any]] = Field(default_factory=list, description="限售解禁")
    announcements: list[dict[str, Any]] = Field(default_factory=list, description="公司公告")
    news: list[dict[str, Any]] = Field(default_factory=list, description="近期新闻")
    upcoming_hints: list[str] = Field(default_factory=list, description="近期事件提示")
    message: str = Field(default="", description="说明信息")
