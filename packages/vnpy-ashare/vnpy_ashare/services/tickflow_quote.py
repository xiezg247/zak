"""TickFlow 行情流（UI 经本模块访问 integrations.tickflow）。"""

from __future__ import annotations

from vnpy_ashare.integrations.tickflow.stream import TickflowStreamBridge, can_use_tickflow_stream

__all__ = ["TickflowStreamBridge", "can_use_tickflow_stream"]
