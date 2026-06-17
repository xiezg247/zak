"""个股概念题材领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class ConceptProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    concepts: list[dict[str, Any]] = Field(default_factory=list, description="概念题材列表")
    message: str = Field(default="", description="说明信息")
