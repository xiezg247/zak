"""NotificationService：规则、格式化、出站调度。"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.notifications.channels.feishu_webhook import FeishuWebhookChannel
from vnpy_ashare.notifications.dispatcher import NotifyDispatcher
from vnpy_ashare.notifications.events import (
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
)
from vnpy_ashare.notifications.formatters import format_notify_text
from vnpy_ashare.notifications.models import NotifyDeliveryResult
from vnpy_ashare.notifications.rules import NotifyRulesEngine
from vnpy_ashare.services.base import BaseService

logger = logging.getLogger(__name__)

_HIT_COUNT_RE = re.compile(r"命中\s*(\d+)\s*条")


class NotificationService(BaseService):
    def __init__(self, engine: Any, *, sync: bool = False) -> None:
        super().__init__(engine)
        self._sync = sync
        self._rules = NotifyRulesEngine()
        self._dispatcher = NotifyDispatcher(
            channel_factory=self._build_channel,
            sync=sync,
        )
        self.last_error: str | None = None

    def reload(self) -> None:
        self._rules.reload_config()

    def shutdown(self) -> None:
        self._dispatcher.shutdown()

    def notify(
        self,
        event_id: str,
        *,
        dedupe_key: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        ok, reason = self._rules.should_send(event_id, dedupe_key)
        if not ok:
            logger.debug("notify skipped event=%s reason=%s", event_id, reason)
            return

        data = dict(payload or {})
        try:
            text = format_notify_text(event_id, data)
        except ValueError:
            logger.exception("unknown notify event=%s", event_id)
            return

        self._rules.mark_sent(event_id, dedupe_key)

        def on_complete(result: NotifyDeliveryResult) -> None:
            if result.success:
                self.last_error = None
            else:
                self.last_error = result.message

        if not self._dispatcher.enqueue(text, on_complete=on_complete):
            self.last_error = "通知队列已满"

    def test_send(self) -> NotifyDeliveryResult:
        ok, reason = self._rules.should_send(NOTIFY_EVENT_MANUAL_TEST, "manual_test")
        if not ok:
            return NotifyDeliveryResult(success=False, message=reason)

        text = format_notify_text(NOTIFY_EVENT_MANUAL_TEST, {})
        result = self._build_channel().send_text(text)
        self.last_error = None if result.success else result.message
        return result

    def on_job_finished(self, job_id: str, result: JobResult) -> None:
        if result.skipped:
            return

        if result.success:
            if job_id == "screen_intraday":
                self.notify(
                    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
                    dedupe_key="screen_intraday",
                    payload=_screener_payload(job_id, result.message),
                )
            elif job_id == "screen_post_close":
                self.notify(
                    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
                    dedupe_key="screen_post_close",
                    payload=_screener_payload(job_id, result.message),
                )
            return

        job_name = self._resolve_job_name(job_id)
        self.notify(
            NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
            dedupe_key=job_id,
            payload={
                "job_id": job_id,
                "job_name": job_name,
                "message": result.message,
            },
        )

    def _build_channel(self) -> FeishuWebhookChannel:
        url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
        return FeishuWebhookChannel(url)

    def _resolve_job_name(self, job_id: str) -> str:
        scheduler = getattr(self.engine, "scheduler", None)
        if scheduler is not None and hasattr(scheduler, "get_job_name"):
            return scheduler.get_job_name(job_id)
        return job_id


def _screener_payload(job_id: str, message: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message, "job_id": job_id}
    hit = _HIT_COUNT_RE.search(message)
    if hit:
        payload["hit_count"] = int(hit.group(1))
    first_line = message.split("（", 1)[0].strip()
    if first_line:
        payload["recipe"] = first_line.split()[0]
    return payload
