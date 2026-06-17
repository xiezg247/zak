"""个股概念/题材。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.concept import fetch_stock_concepts


class ConceptProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    concepts: list[dict[str, Any]] = Field(default_factory=list, description="concepts")
    message: str = Field(default="", description="说明信息")


def build_concept_profile(vt_symbol: str) -> ConceptProfile:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return ConceptProfile(ts_code="", vt_symbol=vt_symbol, message="无法解析代码")

    try:
        concepts = fetch_stock_concepts(item.ts_code)
    except TushareNotConfiguredError:
        return ConceptProfile(
            ts_code=item.ts_code,
            vt_symbol=item.vt_symbol,
            message="未配置 TUSHARE_TOKEN，无法拉取概念板块",
        )
    except Exception as ex:
        return ConceptProfile(
            ts_code=item.ts_code,
            vt_symbol=item.vt_symbol,
            message=str(ex),
        )

    message = ""
    if not concepts:
        message = "暂无概念数据（Tushare concept_detail 未返回）"
    return ConceptProfile(
        ts_code=item.ts_code,
        vt_symbol=item.vt_symbol,
        concepts=concepts,
        message=message,
    )
