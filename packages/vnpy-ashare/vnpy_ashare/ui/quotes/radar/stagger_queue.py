"""错峰队列与防抖定时器（雷达 UI 主线程节流）。"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from typing import Generic, TypeVar

from vnpy.trader.ui import QtCore

T = TypeVar("T")
K = TypeVar("K", bound=Hashable)


class StaggerQueue(Generic[T]):
    """单 shot timer + 队列：首项立即执行，后续按 interval 错峰。"""

    def __init__(
        self,
        parent: QtCore.QObject,
        *,
        interval_ms: int,
        on_item: Callable[[T], None],
    ) -> None:
        self._interval_ms = max(0, int(interval_ms))
        self._on_item = on_item
        self._items: list[T] = []
        self._timer = QtCore.QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

    @property
    def pending(self) -> list[T]:
        return self._items

    def __bool__(self) -> bool:
        return bool(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._timer.stop()

    def stop(self) -> None:
        self._timer.stop()

    def is_idle(self) -> bool:
        return not self._items and not self._timer.isActive()

    def replace(self, items: Sequence[T], *, kick: bool = True) -> None:
        """用新序列覆盖队列；kick 时立即消费首项。"""
        self._items = list(items)
        if kick and self._items:
            self._timer.stop()
            self._tick()

    def extend_unique(
        self,
        items: Sequence[T],
        *,
        key: Callable[[T], K],
        kick: bool = True,
    ) -> None:
        """追加 items；同 key 已在队列中则先移除再追加到队尾。"""
        if not items:
            return
        incoming_keys = {key(item) for item in items}
        self._items = [item for item in self._items if key(item) not in incoming_keys]
        self._items.extend(items)
        if kick and not self._timer.isActive():
            self._tick()

    def upsert_by_key(
        self,
        items: Sequence[T],
        *,
        key: Callable[[T], K],
        kick_if_idle: bool = True,
    ) -> None:
        """按 key 去重后入队；仅当原先空闲时 kick。"""
        if not items:
            return
        was_idle = self.is_idle()
        for item in items:
            item_key = key(item)
            self._items = [existing for existing in self._items if key(existing) != item_key]
            self._items.append(item)
        if kick_if_idle and was_idle:
            self._tick()

    def _tick(self) -> None:
        if not self._items:
            return
        item = self._items.pop(0)
        self._on_item(item)
        if self._items:
            self._timer.start(self._interval_ms)


class DebouncedCall:
    """重复 schedule 会重置倒计时。"""

    def __init__(
        self,
        parent: QtCore.QObject,
        *,
        interval_ms: int,
        callback: Callable[[], None],
    ) -> None:
        self._timer = QtCore.QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(0, int(interval_ms)))
        self._timer.timeout.connect(callback)

    def schedule(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
