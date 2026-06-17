"""个股股东结构。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_common.domain.base import MutableModel
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.corporate import fetch_top10_holders


class HolderProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    end_date: str = Field(default="", description="报告期")
    holders: list[dict[str, Any]] = Field(default_factory=list, description="前十大股东")
    message: str = Field(default="", description="说明信息")


def build_holder_profile(vt_symbol: str) -> HolderProfile:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return HolderProfile(ts_code="", vt_symbol=vt_symbol, message="无法解析代码")

    try:
        holders = fetch_top10_holders(item.ts_code)
    except TushareNotConfiguredError as ex:
        return HolderProfile(
            ts_code=item.ts_code,
            vt_symbol=item.vt_symbol,
            message=str(ex),
        )
    except Exception as ex:
        return HolderProfile(
            ts_code=item.ts_code,
            vt_symbol=item.vt_symbol,
            message=str(ex),
        )

    end_date = holders[0]["end_date"] if holders else ""
    message = ""
    if not holders:
        message = "暂无十大股东数据"
    return HolderProfile(
        ts_code=item.ts_code,
        vt_symbol=item.vt_symbol,
        end_date=end_date,
        holders=holders,
        message=message,
    )
