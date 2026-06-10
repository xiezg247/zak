"""回测历史、落库与 CTA App。"""

from vnpy_ashare.backtest.app import AshareCtaBacktesterApp
from vnpy_ashare.backtest.engine import AshareBacktesterEngine
from vnpy_ashare.backtest.run_store import (
    BacktestRunRecord,
    BatchBacktestSession,
    delete_batch,
    get_backtest_run,
    get_latest_backtest_run,
    list_backtest_runs,
    list_batch_sessions,
    list_runs_by_batch,
    save_backtest_run,
    save_backtest_summary_dict,
)
from vnpy_ashare.backtest.strategy_filter import filter_ashare_strategy_names

__all__ = [
    "AshareCtaBacktesterApp",
    "AshareBacktesterEngine",
    "BacktestRunRecord",
    "BatchBacktestSession",
    "delete_batch",
    "filter_ashare_strategy_names",
    "get_backtest_run",
    "get_latest_backtest_run",
    "list_backtest_runs",
    "list_batch_sessions",
    "list_runs_by_batch",
    "save_backtest_run",
    "save_backtest_summary_dict",
]
