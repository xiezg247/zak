"""批量回测 worker 与半年短区间。"""

from __future__ import annotations

from datetime import datetime

import pytest
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine

from vnpy_ashare.backtest.app import AshareCtaBacktesterApp
from vnpy_ashare.backtest.batch_runner import BacktestTask, run_single_backtest_task
from vnpy_ashare.screener.batch.batch_actions import BatchBacktestParams, run_batch_backtests


def _half_year_params(**kwargs) -> BatchBacktestParams:
    return BatchBacktestParams(
        class_name="AshareDoubleMaStrategy",
        start=datetime(2024, 12, 1),
        end=datetime(2025, 6, 1),
        strategy_setting={"fast_window": 5, "slow_window": 20},
        **kwargs,
    )


def test_run_single_backtest_task_returns_trade_stats() -> None:
    task = BacktestTask(
        vt_symbol="002230.SZSE",
        name="科大讯飞",
        class_name="AshareDoubleMaStrategy",
        interval="d",
        start="2024-12-01",
        end="2025-06-01",
        rate=0.0003,
        slippage=0.0,
        size=100,
        pricetick=0.01,
        capital=100_000,
        setting={"fast_window": 5, "slow_window": 20},
    )
    payload = run_single_backtest_task(task)
    assert not payload["error"]
    assert (payload["total_trade_count"] or 0) > 0


@pytest.mark.parametrize("max_workers", ["1", "2"])
def test_run_batch_backtests_two_symbols_half_year(max_workers: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BATCH_BACKTEST_MAX_WORKERS", max_workers)
    rows = [
        {"vt_symbol": "002230.SZSE", "name": "科大讯飞"},
        {"vt_symbol": "000062.SZSE", "name": "深圳华强"},
    ]
    ee = EventEngine()
    me = MainEngine(ee)
    me.add_app(AshareCtaBacktesterApp)
    results = run_batch_backtests(me, rows, _half_year_params())
    assert len(results) == 2
    for row in results:
        assert not row.error, row.error
        assert (row.total_trade_count or 0) > 0
    ee.stop()
