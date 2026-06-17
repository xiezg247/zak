"""首屏渲染后延迟注册的 App（与 launcher / main_window 解耦，避免循环 import）。"""

from __future__ import annotations

from vnpy.trader.engine import MainEngine
from vnpy_datamanager import DataManagerApp

from vnpy_ashare.backtest.app import AshareCtaBacktesterApp


def register_deferred_apps(main_engine: MainEngine) -> None:
    """首屏渲染后再加载非核心 App，缩短冷启动。"""
    main_engine.add_app(AshareCtaBacktesterApp)
    main_engine.add_app(DataManagerApp)
