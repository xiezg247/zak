"""A 股策略 ArrayManager 预热与短区间回测。"""

from __future__ import annotations

from datetime import datetime
import time

from vnpy.event import EventEngine
from vnpy.trader.constant import Interval
from vnpy.trader.engine import MainEngine

from strategies.double_ma_strategy import AshareDoubleMaStrategy
from vnpy_ashare.backtest.app import AshareCtaBacktesterApp


def _run_half_year_backtest() -> int:
    ee = EventEngine()
    me = MainEngine(ee)
    me.add_app(AshareCtaBacktesterApp)
    engine = me.get_engine("CtaBacktester")
    engine.init_engine()
    setting = {k: getattr(AshareDoubleMaStrategy, k) for k in AshareDoubleMaStrategy.parameters}
    engine.start_backtesting(
        "AshareDoubleMaStrategy",
        "002230.SZSE",
        Interval.DAILY.value,
        datetime(2024, 12, 1),
        datetime(2025, 6, 1),
        0.00045,
        0.01,
        1,
        0.01,
        100_000,
        setting,
    )
    for _ in range(400):
        if engine.thread is None:
            break
        time.sleep(0.05)
    stats = engine.get_result_statistics() or {}
    trade_count = int(stats.get("total_trade_count") or 0)
    ee.stop()
    return trade_count


def test_double_ma_half_year_backtest_has_trades() -> None:
    assert _run_half_year_backtest() > 0


def test_indicator_warmup_matches_array_manager_size() -> None:
    strategy = AshareDoubleMaStrategy(None, "test", "002230.SZSE", {})
    warmup = strategy.indicator_warmup_bars()
    am = strategy.init_array_manager()
    assert am.size == warmup
    assert warmup == max(strategy.fast_window, strategy.slow_window) + 5
