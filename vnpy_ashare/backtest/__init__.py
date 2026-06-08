"""回测历史与落库。"""

from vnpy_ashare.backtest.run_store import (
    BacktestRunRecord,
    get_backtest_run,
    get_latest_backtest_run,
    list_backtest_runs,
    save_backtest_run,
    save_backtest_summary_dict,
)

__all__ = [
    "BacktestRunRecord",
    "get_backtest_run",
    "get_latest_backtest_run",
    "list_backtest_runs",
    "save_backtest_run",
    "save_backtest_summary_dict",
]
