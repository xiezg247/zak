"""VeighNa App 入口。"""

from __future__ import annotations

from pathlib import Path

from vnpy.trader.app import BaseApp

from vnpy_llm.app.engine import APP_NAME, LlmEngine

__all__ = ["LlmApp"]


class LlmApp(BaseApp):
    app_name: str = APP_NAME
    app_module: str = "vnpy_llm"
    app_path: Path = Path(__file__).resolve().parent.parent
    display_name: str = "AI助手"
    engine_class: type[LlmEngine] = LlmEngine
    icon_name: str = ""
    widget_name: str = "LlmManagerWidget"
