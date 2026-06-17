"""分 K 封板时间测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.signals.intraday_seal_time import (
    detect_seal_time_from_minute_bars,
    infer_prev_close_from_row,
)


@dataclass
class _Bar:
    datetime: datetime
    high_price: float


def test_detect_seal_time_from_minute_bars() -> None:
    bars = [
        _Bar(datetime(2025, 6, 17, 9, 35, tzinfo=CHINA_TZ), 10.5),
        _Bar(datetime(2025, 6, 17, 10, 2, tzinfo=CHINA_TZ), 11.0),
    ]
    assert detect_seal_time_from_minute_bars(bars, limit_price=11.0) == "100200"


def test_infer_prev_close_from_row() -> None:
    row = {"last_price": 11.0, "change_pct": 10.0}
    assert infer_prev_close_from_row(row) == 10.0
