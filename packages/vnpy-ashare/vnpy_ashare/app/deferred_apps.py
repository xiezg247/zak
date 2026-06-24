"""首屏渲染后按需注册的 App（与 launcher / main_window 解耦，避免循环 import）。"""

from __future__ import annotations

from vnpy.trader.engine import MainEngine
from vnpy_datamanager import DataManagerApp

from vnpy_ashare.backtest.app import AshareCtaBacktesterApp
from vnpy_common.startup_profile import profiler

_cta_backtester_registered = False
_data_manager_registered = False


def ensure_cta_backtester_app(main_engine: MainEngine) -> None:
    """打开策略回测页或从选股跳转回测时加载。"""
    global _cta_backtester_registered
    if _cta_backtester_registered:
        return
    with profiler.phase("add_app(AshareCtaBacktesterApp)"):
        main_engine.add_app(AshareCtaBacktesterApp)
    _cta_backtester_registered = True


def ensure_data_manager_app(main_engine: MainEngine) -> None:
    """打开数据管理弹窗时加载。"""
    global _data_manager_registered
    if _data_manager_registered:
        return
    with profiler.phase("add_app(DataManagerApp)"):
        main_engine.add_app(DataManagerApp)
    _data_manager_registered = True
