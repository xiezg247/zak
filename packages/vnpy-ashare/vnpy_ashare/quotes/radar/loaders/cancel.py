"""雷达批量加载协作式取消（Worker request_cancel → loader 提前退出）。"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar

_cancel_check: ContextVar[Callable[[], bool] | None] = ContextVar("radar_load_cancel_check", default=None)


class RadarLoadCancelled(Exception):
    """当前雷达加载任务已被取消。"""


def bind_radar_load_cancel(check: Callable[[], bool]) -> Callable[[], None]:
    token = _cancel_check.set(check)

    def reset() -> None:
        _cancel_check.reset(token)

    return reset


def radar_load_cancelled() -> bool:
    check = _cancel_check.get()
    return bool(check()) if check is not None else False


def raise_if_radar_load_cancelled() -> None:
    if radar_load_cancelled():
        raise RadarLoadCancelled()
