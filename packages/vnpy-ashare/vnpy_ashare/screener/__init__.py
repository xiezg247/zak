"""选股（P0 行情 + P1 Tushare 基本面）。

目录约定：
- ``run/``：执行、run_store、导出
- ``recipe/``：多维度配方
- ``preset/``：内置方案与规则
- ``pattern/``：形态选股
- ``data/``：选股数据源编排（Redis + Tushare 合并）
- ``dimensions/``：配方维度实现
- ``batch/``：批量回测 / 下载
- ``draft/``：AI 草稿与 NL
- ``auto/``、``reference/``、``sector/``、``sentiment/``
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "BatchBacktestParams",
    "BatchBacktestRow",
    "MarketQuotesLoadError",
    "SavedScheme",
    "ScreenerRequest",
    "ScreenerRunRecord",
    "ScreenerRunResult",
    "TushareNotConfiguredError",
    "batch_download_daily_bars",
    "build_scheme_config",
    "delete_run",
    "delete_scheme",
    "export_rows_to_csv",
    "get_latest_run",
    "get_run",
    "list_all_preset_names",
    "list_runs",
    "list_schemes",
    "load_batch_backtest_defaults",
    "load_market_quote_rows",
    "resolve_export_columns",
    "resolve_preset_input",
    "rows_to_stock_items",
    "run_batch_backtests",
    "run_screener",
    "save_run",
    "save_scheme",
]


def __getattr__(name: str) -> Any:
    if name == "TushareNotConfiguredError":
        from vnpy_ashare.integrations.tushare import TushareNotConfiguredError

        return TushareNotConfiguredError
    if name in {"MarketQuotesLoadError", "load_market_quote_rows"}:
        from vnpy_ashare.screener.data import quotes_loader as _quotes_loader

        return getattr(_quotes_loader, name)
    if name in {
        "BatchBacktestParams",
        "BatchBacktestRow",
        "batch_download_daily_bars",
        "load_batch_backtest_defaults",
        "rows_to_stock_items",
        "run_batch_backtests",
    }:
        from vnpy_ashare.screener.batch import batch_actions as _batch_actions

        return getattr(_batch_actions, name)
    if name in {"SavedScheme", "delete_scheme", "list_schemes", "save_scheme"}:
        from vnpy_ashare.screener.preset import scheme_store as _scheme_store

        return getattr(_scheme_store, name)
    if name in {
        "ScreenerRequest",
        "ScreenerRunResult",
        "build_scheme_config",
        "export_rows_to_csv",
        "list_all_preset_names",
        "resolve_export_columns",
        "resolve_preset_input",
        "run_screener",
    }:
        from vnpy_ashare.screener.run import runner as _runner

        return getattr(_runner, name)
    if name == "ScreenerRunRecord":
        from vnpy_ashare.screener.run.run_store import ScreenerRunRecord

        return ScreenerRunRecord
    if name in {"delete_run", "get_latest_run", "get_run", "list_runs", "save_run"}:
        from vnpy_ashare.screener.run import run_store as _run_store

        return getattr(_run_store, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
