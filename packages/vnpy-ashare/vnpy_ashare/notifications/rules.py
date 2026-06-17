"""通知发送规则：开关、订阅、去重、全局限频。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from vnpy_ashare.notifications.events import DEFAULT_EVENT_SUBSCRIPTIONS, NOTIFY_EVENT_MANUAL_TEST
from vnpy_ashare.notifications.prefs import load_notify_prefs

_DEDUPE_WINDOW_SEC = 300.0
_DEFAULT_MIN_INTERVAL_SEC = 30


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


class NotifyRulesEngine:
    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._last_sent_at: float | None = None
        self._dedupe_at: dict[tuple[str, str], float] = {}
        self.reload_config()

    def reload_config(self) -> None:
        self._enabled = _env_bool("NOTIFY_ENABLED", default=False)
        self._webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
        self._min_interval_sec = float(_env_int("NOTIFY_MIN_INTERVAL_SEC", default=_DEFAULT_MIN_INTERVAL_SEC))
        self._subscriptions = dict(load_notify_prefs().event_subscriptions)
        for event_id, default in DEFAULT_EVENT_SUBSCRIPTIONS.items():
            self._subscriptions.setdefault(event_id, default)

    @property
    def webhook_configured(self) -> bool:
        return bool(self._webhook_url)

    def should_send(self, event_id: str, dedupe_key: str | None) -> tuple[bool, str]:
        if not self._enabled:
            return False, "通知总开关已关闭"
        if not self._webhook_url:
            return False, "未配置 FEISHU_WEBHOOK_URL"
        if event_id == NOTIFY_EVENT_MANUAL_TEST:
            return True, ""
        if not self._subscriptions.get(event_id, False):
            return False, f"事件未订阅：{event_id}"

        now = self._clock()
        if self._min_interval_sec > 0 and self._last_sent_at is not None:
            elapsed = now - self._last_sent_at
            if elapsed < self._min_interval_sec:
                return False, f"全局限频（{int(self._min_interval_sec)}s）"

        key = dedupe_key or event_id
        dedupe_at = self._dedupe_at.get((event_id, key))
        if dedupe_at is not None and now - dedupe_at < _DEDUPE_WINDOW_SEC:
            return False, "去重窗口内"

        return True, ""

    def mark_sent(self, event_id: str, dedupe_key: str | None) -> None:
        now = self._clock()
        self._last_sent_at = now
        key = dedupe_key or event_id
        self._dedupe_at[(event_id, key)] = now
