"""回测历史与落库。"""

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

__all__ = [
    "BacktestRunRecord",
    "BatchBacktestSession",
    "delete_batch",
    "get_backtest_run",
    "get_latest_backtest_run",
    "list_backtest_runs",
    "list_batch_sessions",
    "list_runs_by_batch",
    "save_backtest_run",
    "save_backtest_summary_dict",
]
