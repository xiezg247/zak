"""持仓异动通知扫描输入（与 QuotesPage 解耦）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.trading.position import PositionSnapshot


@dataclass(frozen=True)
class PositionAlertRow:
    vt_symbol: str
    name: str
    symbol: str
    snap: PositionSnapshot
    quote: QuoteSnapshot | None


@dataclass(frozen=True)
class PositionAlertScanInput:
    enabled: bool
    rows: tuple[PositionAlertRow, ...] = ()
