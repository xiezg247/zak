"""通知出站队列与 Worker。"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

from vnpy_ashare.notifications.channels.feishu_webhook import FeishuWebhookChannel
from vnpy_ashare.notifications.models import NotifyDeliveryResult, NotifyOutboundMessage

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 50


@dataclass(frozen=True)
class _QueuedMessage:
    event_id: str
    outbound: NotifyOutboundMessage
    payload: dict
    on_complete: Callable[[str, dict, NotifyDeliveryResult], None] | None = None


class NotifyDispatcher:
    def __init__(
        self,
        *,
        channel_factory: Callable[[], FeishuWebhookChannel],
        sync: bool = False,
    ) -> None:
        self._channel_factory = channel_factory
        self._sync = sync
        self._queue: queue.Queue[_QueuedMessage | None] = queue.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        if not sync:
            self._worker = threading.Thread(target=self._run, name="notify-dispatcher", daemon=True)
            self._worker.start()

    def enqueue(
        self,
        event_id: str,
        outbound: NotifyOutboundMessage,
        *,
        payload: dict | None = None,
        on_complete: Callable[[str, dict, NotifyDeliveryResult], None] | None = None,
    ) -> bool:
        data = dict(payload or {})
        item = _QueuedMessage(event_id=event_id, outbound=outbound, payload=data, on_complete=on_complete)
        if self._sync:
            result = self._deliver(outbound)
            if on_complete is not None:
                on_complete(event_id, data, result)
            return result.success

        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            logger.warning("notify queue full, message dropped")
            return False

    def shutdown(self, *, timeout_sec: float = 2.0) -> None:
        self._stop.set()
        if self._worker is None:
            return
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._worker.join(timeout=timeout_sec)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            result = self._deliver(item.outbound)
            if item.on_complete is not None:
                try:
                    item.on_complete(item.event_id, item.payload, result)
                except Exception:
                    logger.exception("notify on_complete failed")

    def _deliver(self, outbound: NotifyOutboundMessage) -> NotifyDeliveryResult:
        channel = self._channel_factory()
        return channel.send_outbound(outbound)
