"""自选多维看盘行模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WatchlistMultiSortKey = Literal["sort_order", "change_pct", "anomaly_score"]


@dataclass(frozen=True)
class WatchlistMultiRow:
    vt_symbol: str
    symbol: str
    name: str
    sort_order: int

    last_price: float | None
    change_pct: float | None
    volume_ratio: float | None
    turnover_rate: float | None
    change_speed_5m: float | None

    metric_label: str
    metric_value: str
    sub_label: str
    sub_value: str
    anomaly_score: float

    signal_label: str | None = None
    has_position: bool = False
    position_pnl_pct: float | None = None
    industry: str | None = None
    sector_rank: int | None = None
    sector_avg_change: float | None = None
    sparkline_points: tuple[float, ...] = ()
    sparkline_kind: Literal["daily", "intraday", "none"] = "none"


@dataclass(frozen=True)
class WatchlistMultiBoardData:
    rows: tuple[WatchlistMultiRow, ...]
    empty_message: str = ""
    total_count: int = 0
