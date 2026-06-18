"""vnpy_tickflow：TickFlow 数据源与共享客户端。

VeighNa ``get_datafeed()`` 约定：``vnpy_tickflow.Datafeed``（见 ``datafeed.TickflowDatafeed``）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["Datafeed"]

if TYPE_CHECKING:
    from vnpy_tickflow.datafeed import TickflowDatafeed as Datafeed


def __getattr__(name: str) -> Any:
    if name == "Datafeed":
        from vnpy_tickflow.datafeed import TickflowDatafeed

        return TickflowDatafeed
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
