"""GUI 启动入口。"""

from __future__ import annotations

import os
import sys

import vnpy_ashare.app._macos_qt_bootstrap  # noqa: F401 — 须在 Qt 之前加载

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy_common.ui.qt_app import create_zak_qapp

from vnpy_ashare.app.bootstrap import install_shared_bridges
from vnpy_ashare.app.branding import QAPP_NAME
from vnpy_ashare.app.plugin import AshareApp
from vnpy_ashare.config.fonts import resolve_font_family
from vnpy_ashare.config.runtime import ensure_runtime_config
from vnpy_ashare.config.vt_settings import ensure_vt_settings_from_env, reload_vnpy_settings
from vnpy_ashare.integrations.tickflow.stream import shutdown_all_tickflow_streams
from vnpy_ashare.ui.shell.main_window import AshareMainWindow
from vnpy_common.paths import PROJECT_ROOT
from vnpy_common.platform.macos_gui import bootstrap_macos_gui_runtime
from vnpy_common.startup_profile import profiler


def _optional_llm_app():
    try:
        from vnpy_llm.app.plugin import LlmApp

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
    with profiler.phase("prepare_runtime"):
        _prepare_runtime()
    with profiler.phase("install_shared_bridges"):
        install_shared_bridges()

    with profiler.phase("vt_settings"):
        if ensure_vt_settings_from_env():
            reload_vnpy_settings()
            print("已从 .env 生成或重建 vt_setting.json（~/.vntrader/）")

    with profiler.phase("runtime_config"):
        if ensure_runtime_config():
            print("已应用 A 股回测默认参数（~/.vntrader/cta_backtester_setting.json）")

    with profiler.phase("create_qapp"):
        qapp = create_zak_qapp(QAPP_NAME)
        bootstrap_macos_gui_runtime(before_qt=False)
        qapp.setStyle("Fusion")

    qapp.aboutToQuit.connect(shutdown_all_tickflow_streams)

    with profiler.phase("event_engine"):
        event_engine = EventEngine()
    with profiler.phase("main_engine"):
        main_engine = MainEngine(event_engine)

    with profiler.phase("add_app(AshareApp)"):
        main_engine.add_app(AshareApp)
    with profiler.phase("optional_llm_import"):
        llm_app = _optional_llm_app()
    if llm_app is not None:
        with profiler.phase("add_app(LlmApp)"):
            main_engine.add_app(llm_app)

    with profiler.phase("main_window"):
        main_window = AshareMainWindow(main_engine, event_engine)
        main_window.showMaximized()

    profiler.finish("startup until window visible")
    main_window.schedule_initial_page()

    qapp.exec()
