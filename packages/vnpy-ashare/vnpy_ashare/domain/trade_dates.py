"""交易日遍历（领域层，无 screener / quotes 依赖）。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from vnpy_ashare.domain.calendar import last_trading_day

DEFAULT_LOOKBACK_DAYS = 10


def iter_trade_date_strs(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> Iterator[str]:
    """从 start（默认最近交易日）向前遍历交易日。"""
    current = start or last_trading_day()
    for _ in range(max(1, max_lookback)):
        yield current.strftime("%Y%m%d")
        current = last_trading_day(on_or_before=current - timedelta(days=1))
