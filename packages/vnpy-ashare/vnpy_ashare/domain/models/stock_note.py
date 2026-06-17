"""个股笔记领域模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockNoteMemo:
    symbol: str
    exchange: str
    body: str
    updated_at: str


@dataclass(frozen=True)
class StockNoteEntry:
    id: int
    symbol: str
    exchange: str
    body: str
    created_at: str


@dataclass(frozen=True)
class StockNoteBundle:
    symbol: str
    exchange: str
    memo: StockNoteMemo | None
    entries: list[StockNoteEntry]


@dataclass(frozen=True)
class StockNoteIndexRow:
    """笔记中心列表行：按标的聚合备忘与流水摘要。"""

    symbol: str
    exchange: str
    name: str = ""
    memo_preview: str = ""
    has_memo: bool = False
    entry_count: int = 0
    report_count: int = 0
    memo_updated_at: str = ""
    latest_entry_at: str = ""
    latest_report_at: str = ""
    last_activity_at: str = ""

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


@dataclass(frozen=True)
class StockAnalysisReport:
    id: int
    symbol: str
    exchange: str
    title: str
    body: str
    source_scope: str
    context_json: str
    summary: str
    created_at: str
    updated_at: str

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"
