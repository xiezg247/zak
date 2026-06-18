"""VeighNa App 入口。"""

from __future__ import annotations

from pathlib import Path

from vnpy.trader.app import BaseApp

from vnpy_ashare.app.engine import APP_NAME, AshareEngine

__all__ = ["AshareApp"]


class AshareApp(BaseApp):
    """A 股行情 App（市场 / 自选 / 本地由主窗口侧栏切换）。"""

    app_name: str = "Ashare"
    app_module: str = "vnpy_ashare"
    app_path: Path = Path(__file__).resolve().parent.parent
    display_name: str = "A股行情"
    engine_class: type[AshareEngine] = AshareEngine
    icon_name: str = ""
    widget_name: str = "WatchlistPageWidget"
