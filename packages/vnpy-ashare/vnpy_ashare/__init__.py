"""VeighNa A 股行情应用（市场 / 自选 / 本地）。"""

from pathlib import Path

from vnpy.trader.app import BaseApp

from .app.engine import APP_NAME, AshareEngine

__all__ = [
    "APP_NAME",
    "AshareApp",
    "AshareEngine",
]

__version__ = "0.1.0"


class AshareApp(BaseApp):
    """A 股行情 App（市场 / 自选 / 本地由主窗口侧栏切换）。"""

    app_name: str = "Ashare"
    app_module: str = __name__
    app_path: Path = Path(__file__).parent
    display_name: str = "A股行情"
    engine_class: type[AshareEngine] = AshareEngine
    icon_name: str = ""
    widget_name: str = "WatchlistPageWidget"
