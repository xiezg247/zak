"""AshareEngine 与 Service 访问辅助。"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine
    from vnpy_ashare.engine import AshareEngine

T = TypeVar("T")


def get_ashare_engine(main_engine: MainEngine | None) -> AshareEngine | None:
    if main_engine is None:
        return None
    from vnpy_ashare.engine import APP_NAME, AshareEngine

    engine = main_engine.get_engine(APP_NAME)
    if isinstance(engine, AshareEngine):
        return engine
    return None


def get_service(main_engine: MainEngine | None, name: str):
    engine = get_ashare_engine(main_engine)
    if engine is None:
        return None
    return getattr(engine, name, None)
