"""本地分 K 进程内缓存测试。"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from vnpy_ashare.trading.signals.limit_board_intraday import (
    clear_local_minute_bars_cache,
    load_local_minute_bars_for_date,
)


def test_load_local_minute_bars_for_date_uses_process_cache() -> None:
    clear_local_minute_bars_cache()
    trade_date = date(2026, 6, 17)
    bars = [object()]
    with patch(
        "vnpy_ashare.trading.signals.limit_board_intraday.load_period_bars",
        return_value=bars,
    ) as loader:
        first = load_local_minute_bars_for_date("600000.SSE", trade_date)
        second = load_local_minute_bars_for_date("600000.SSE", trade_date)
    assert first is second
    loader.assert_called_once()
