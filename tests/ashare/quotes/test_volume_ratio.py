"""盘中量比计算测试。"""

from datetime import datetime
from unittest.mock import patch

from vnpy_ashare.domain.time.market_hours import CHINA_TZ, INTRADAY_SESSION_MINUTES, elapsed_trading_minutes
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.quotes.misc.volume_ratio import compute_intraday_volume_ratio, fill_intraday_volume_ratios


def _quote(*, volume: float = 1000.0, volume_ratio: float = 0.0) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="600000.SH",
        name="测试",
        last_price=10.0,
        prev_close=9.8,
        open_price=9.9,
        high_price=10.1,
        low_price=9.8,
        change_amount=0.2,
        change_pct=2.0,
        turnover_rate=1.0,
        volume=volume,
        volume_ratio=volume_ratio,
    )


def test_compute_intraday_volume_ratio_at_half_session() -> None:
    # 60 分钟时成交量 12000 手，5 日均量 24000 手 → 量比 2.0
    dt = datetime(2026, 6, 16, 10, 30, tzinfo=CHINA_TZ)
    ratio = compute_intraday_volume_ratio(12000.0, 24000.0, dt=dt)
    assert ratio == 2.0


def test_elapsed_trading_minutes_after_close() -> None:
    dt = datetime(2026, 6, 16, 15, 30, tzinfo=CHINA_TZ)
    assert elapsed_trading_minutes(dt) == float(INTRADAY_SESSION_MINUTES)


def test_fill_intraday_volume_ratios() -> None:
    quotes = {"600000.SH": _quote(volume=12000.0)}
    dt = datetime(2026, 6, 16, 10, 30, tzinfo=CHINA_TZ)
    with patch(
        "vnpy_ashare.quotes.misc.volume_ratio.load_avg_daily_volume_map_by_tickflow",
        return_value={"600000.SH": 24000.0},
    ):
        fill_intraday_volume_ratios(quotes, dt=dt)
    assert quotes["600000.SH"].volume_ratio == 2.0


def test_fill_intraday_skips_when_tushare_ratio_exists() -> None:
    quotes = {"600000.SH": _quote(volume=12000.0, volume_ratio=3.5)}
    dt = datetime(2026, 6, 16, 10, 30, tzinfo=CHINA_TZ)
    with patch(
        "vnpy_ashare.quotes.misc.volume_ratio.load_avg_daily_volume_map_by_tickflow",
        return_value={"600000.SH": 24000.0},
    ) as loader:
        fill_intraday_volume_ratios(quotes, dt=dt)
    assert quotes["600000.SH"].volume_ratio == 3.5
    loader.assert_not_called()
