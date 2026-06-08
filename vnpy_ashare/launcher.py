"""GUI 启动入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.ui import create_qapp

from vnpy_ashare import AshareApp
from vnpy_ashare.config import ensure_runtime_config
from vnpy_ashare.paths import PROJECT_ROOT
from vnpy_ashare.ui.fonts import resolve_font_family
from vnpy_ashare.ui.main_window import AshareMainWindow
from vnpy_ashare.backtester_app import AshareCtaBacktesterApp
from vnpy_datamanager import DataManagerApp
from vnpy_llm import LlmApp

import vnpy_tushare  # noqa: F401
import vnpy_tickflow  # noqa: F401


def _prepare_runtime() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    os.chdir(PROJECT_ROOT)
    SETTINGS["font.family"] = resolve_font_family(SETTINGS.get("font.family"))
    SETTINGS["font.size"] = int(SETTINGS.get("font.size", 12))


def main() -> None:
    _prepare_runtime()

    if ensure_runtime_config():
        print("已应用 A 股回测默认参数（~/.vntrader/cta_backtester_setting.json）")

    qapp = create_qapp("vnpy_zak - A股量化终端")

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    main_engine.add_app(AshareApp)
    main_engine.add_app(AshareCtaBacktesterApp)
    main_engine.add_app(DataManagerApp)
    main_engine.add_app(LlmApp)

    main_window = AshareMainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()
