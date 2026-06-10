"""Service 基类。

每个 Service 挂载在 AshareEngine 上，持有 ``main_engine`` / ``event_engine``，
作为 UI 与领域模块（bar_store、screener、context_store）之间的门面层。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.app.engine import AshareEngine


class BaseService:
    """通过 AshareEngine 注入依赖的 Service 基类。"""

    def __init__(self, engine: AshareEngine) -> None:
        self.engine = engine
        self.main_engine: MainEngine = engine.main_engine
        self.event_engine: EventEngine = engine.event_engine
