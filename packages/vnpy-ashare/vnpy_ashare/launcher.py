"""GUI 启动入口。"""

from __future__ import annotations

import os
import sys

import vnpy_tushare  # noqa: F401
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.ui import create_qapp
from vnpy_datamanager import DataManagerApp

import vnpy_tickflow  # noqa: F401
from vnpy_ashare import AshareApp
from vnpy_ashare.backtester_app import AshareCtaBacktesterApp
from vnpy_ashare.bootstrap import install_shared_bridges
from vnpy_ashare.branding import QAPP_NAME
from vnpy_ashare.config import ensure_runtime_config
from vnpy_ashare.ui.fonts import resolve_font_family
from vnpy_ashare.ui.main_window import AshareMainWindow
from vnpy_ashare.vt_settings import ensure_vt_settings_from_env, reload_vnpy_settings
from vnpy_common.paths import PROJECT_ROOT


def _optional_llm_app():
    try:
        from vnpy_llm import LlmApp

        return LlmApp
    except ImportError:
        return None


def _prepare_runtime() -> None:
    os.environ.setdefault("ZAK_PROJECT_ROOT", str(PROJECT_ROOT))
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    os.chdir(PROJECT_ROOT)
    SETTINGS["font.family"] = resolve_font_family(SETTINGS.get("font.family"))
    SETTINGS["font.size"] = int(SETTINGS.get("font.size", 12))


def main() -> None:
    _prepare_runtime()
    install_shared_bridges()

    if ensure_vt_settings_from_env():
        reload_vnpy_settings()
        print("已从 .env 生成或重建 vt_setting.json（~/.vntrader/）")

    if ensure_runtime_config():
        print("已应用 A 股回测默认参数（~/.vntrader/cta_backtester_setting.json）")

    qapp = create_qapp(QAPP_NAME)
    qapp.setStyle("Fusion")

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    main_engine.add_app(AshareApp)
    main_engine.add_app(AshareCtaBacktesterApp)
    main_engine.add_app(DataManagerApp)
    llm_app = _optional_llm_app()
    if llm_app is not None:
        main_engine.add_app(llm_app)

    main_window = AshareMainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()
