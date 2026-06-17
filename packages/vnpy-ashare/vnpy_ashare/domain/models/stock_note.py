"""个股笔记领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class StockNoteMemo(FrozenModel):
    symbol: str = Field(description="六位股票代码")
    exchange: str = Field(description="交易所代码（SSE/SZSE/BSE）")
    body: str = Field(description="备忘正文")
    updated_at: str = Field(description="最后更新时间（ISO 字符串）")


class StockNoteEntry(FrozenModel):
    id: int = Field(description="流水记录主键")
    symbol: str = Field(description="六位股票代码")
    exchange: str = Field(description="交易所代码")
    body: str = Field(description="流水正文")
    created_at: str = Field(description="创建时间（ISO 字符串）")


class StockNoteBundle(FrozenModel):
    symbol: str = Field(description="六位股票代码")
    exchange: str = Field(description="交易所代码")
    memo: StockNoteMemo | None = Field(description="当前备忘（可为空）")
    entries: list[StockNoteEntry] = Field(description="历史流水列表")


class StockNoteIndexRow(FrozenModel):
    """笔记中心列表行：按标的聚合备忘与流水摘要。"""

    symbol: str = Field(description="六位股票代码")
    exchange: str = Field(description="交易所代码")
    name: str = Field(default="", description="证券简称")
    memo_preview: str = Field(default="", description="备忘摘要预览")
    has_memo: bool = Field(default=False, description="是否存在备忘")
    entry_count: int = Field(default=0, description="流水条数")
    report_count: int = Field(default=0, description="分析报告条数")
    memo_updated_at: str = Field(default="", description="备忘最后更新时间")
    latest_entry_at: str = Field(default="", description="最近流水时间")
    latest_report_at: str = Field(default="", description="最近报告时间")
    last_activity_at: str = Field(default="", description="最近活动时间（排序用）")

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


class StockAnalysisReport(FrozenModel):
    id: int = Field(description="报告主键")
    symbol: str = Field(description="六位股票代码")
    exchange: str = Field(description="交易所代码")
    title: str = Field(description="报告标题")
    body: str = Field(description="报告正文（Markdown）")
    source_scope: str = Field(description="生成来源范围标识")
    context_json: str = Field(description="生成时上下文 JSON")
    summary: str = Field(description="报告摘要")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"
