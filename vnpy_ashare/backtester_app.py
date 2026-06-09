"""A 股 CTA 回测 App：注册 AshareBacktesterEngine。"""

from __future__ import annotations

from pathlib import Path

import vnpy_ctabacktester
from vnpy.trader.app import BaseApp
from vnpy_ctabacktester.engine import APP_NAME

from vnpy_ashare.backtester_engine import AshareBacktesterEngine

_CTAB_ROOT = Path(vnpy_ctabacktester.__file__).resolve().parent


class AshareCtaBacktesterApp(BaseApp):
    app_name: str = APP_NAME
    # 沿用 vnpy 包路径，供 MainWindow.init_menu 加载 vnpy_ctabacktester.ui
    app_module: str = "vnpy_ctabacktester"
    app_path: Path = _CTAB_ROOT
    display_name: str = "策略回测"
    engine_class: type[AshareBacktesterEngine] = AshareBacktesterEngine
    widget_name: str = "BacktesterManager"
    icon_name: str = str(_CTAB_ROOT.joinpath("ui", "backtester.ico"))
