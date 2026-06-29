"""Redis Pub/Sub 行情更新通知（Leader collect → GUI 推送刷新，替代部分轮询）。"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})
QUOTE_NOTIFY_CHANNEL = "zak:notify:quotes"


def quote_redis_notify_enabled() -> bool:
    return os.environ.get("ZAK_QUOTE_REDIS_NOTIFY", "").strip().lower() in _TRUTHY


def publish_quote_updated(*, seq: int, client=None) -> None:
    """collect 写 Redis 后广播 seq（订阅方据此刷新 UI / 失效 L1）。"""
    if not quote_redis_notify_enabled() or seq <= 0:
        return
    try:
        from vnpy_ashare.quotes.core.redis_store import create_redis_client

        redis_client = client or create_redis_client()
        redis_client.publish(QUOTE_NOTIFY_CHANNEL, str(seq))
    except Exception:
        logger.debug("publish_quote_updated failed seq=%s", seq, exc_info=True)


def run_quote_notify_listener(
    *,
    on_seq: Callable[[int], None],
    stop: threading.Event,
    poll_timeout_sec: float = 1.0,
) -> None:
    """阻塞监听直到 ``stop`` 置位（在后台线程调用）。"""
    if not quote_redis_notify_enabled():
        return
    try:
        from vnpy_ashare.quotes.core.redis_store import create_redis_client
    except Exception:
        logger.debug("quote notify listener: redis client unavailable", exc_info=True)
        return

    client = create_redis_client()
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(QUOTE_NOTIFY_CHANNEL)
    try:
        while not stop.is_set():
            message = pubsub.get_message(timeout=poll_timeout_sec)
            if not message or message.get("type") != "message":
                continue
            raw = message.get("data")
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw or "")
            try:
                seq = int(text.strip())
            except ValueError:
                continue
            if seq > 0:
                on_seq(seq)
    finally:
        try:
            pubsub.unsubscribe(QUOTE_NOTIFY_CHANNEL)
            pubsub.close()
        except Exception:
            logger.debug("quote notify listener cleanup failed", exc_info=True)
