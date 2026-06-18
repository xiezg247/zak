"""NotificationService：规则、格式化、出站调度。"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from vnpy_ashare.domain.screener.run_result import ScreenerRunResult
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.notifications.channels.feishu_webhook import FeishuWebhookChannel
from vnpy_ashare.notifications.content.delivery import build_notify_outbound
from vnpy_ashare.notifications.core.events import (
    NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_RADAR_LEADER_READY,
    NOTIFY_EVENT_RISK_GATE_CHANGE,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
)
from vnpy_ashare.notifications.core.models import NotifyDeliveryResult
from vnpy_ashare.notifications.pipeline.dispatcher import NotifyDispatcher
from vnpy_ashare.notifications.rules.engine import NotifyRulesEngine
from vnpy_ashare.notifications.triggers.radar_leader_ready import build_radar_leader_ready_payload
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot, classify_emotion_cycle
from vnpy_ashare.quotes.market.emotion_cycle_inputs import EmotionCycleInputs, build_emotion_cycle_inputs
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage.repositories.notify_delivery_log import append_notify_delivery_log
from vnpy_ashare.trading.risk.gate import RiskGateSnapshot

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
            outbound = build_notify_outbound(event_id, data)
        except ValueError:
            logger.exception("unknown notify event=%s", event_id)
            return

        self._rules.mark_sent(event_id, dedupe_key)

        def on_complete(
            completed_event_id: str,
            completed_payload: dict,
            result: NotifyDeliveryResult,
        ) -> None:
            if result.success:
                self.last_error = None
            else:
                self.last_error = result.message
            try:
                append_notify_delivery_log(
                    event_type=completed_event_id,
                    payload=completed_payload,
                    status="ok" if result.success else "failed",
                    error="" if result.success else result.message,
                )
            except Exception:
                logger.exception("notify delivery log write failed")

        if not self._dispatcher.enqueue(
            event_id,
            outbound,
            payload=data,
            on_complete=on_complete,
        ):
            self.last_error = "通知队列已满"

    def publish_emotion_cycle(self, inputs: EmotionCycleInputs) -> EmotionCycleSnapshot:
        tracker = getattr(self.engine, "emotion_cycle_tracker", None)
        if tracker is None:
            return classify_emotion_cycle(inputs)
        changed = tracker.update(inputs)
        snapshot = tracker.last_snapshot
        if changed is not None:
            self._notify_emotion_stage_change(changed)
        assert snapshot is not None
        return snapshot

    def on_market_breadth(self, breadth: MarketBreadthSnapshot) -> None:

        self.publish_emotion_cycle(build_emotion_cycle_inputs(breadth))

    def evaluate_risk_gate(self, *, avg_float_pnl_pct: float | None = None) -> None:
        gate = getattr(self.engine, "risk_gate_engine", None)
        if gate is None:
            return
        changed = gate.evaluate(avg_float_pnl_pct=avg_float_pnl_pct)
        if changed is None:
            return
        self._notify_risk_gate_change(changed)

    def publish_radar_leader_ready(
        self,
        result: ScreenerRunResult,
        config: dict[str, Any] | None = None,
    ) -> None:
        payload = build_radar_leader_ready_payload(result, config)
        if payload is None:
            return
        trade_date = str(result.updated_at or "")[:10] or "unknown"
        variant = str(payload.get("variant") or "mainline")
        self.notify(
            NOTIFY_EVENT_RADAR_LEADER_READY,
            dedupe_key=f"{trade_date}:{variant}",
            payload=payload,
        )

    def test_send(self) -> NotifyDeliveryResult:
        ok, reason = self._rules.should_send(NOTIFY_EVENT_MANUAL_TEST, "manual_test")
        if not ok:
            return NotifyDeliveryResult(success=False, message=reason)

        outbound = build_notify_outbound(NOTIFY_EVENT_MANUAL_TEST, {})
        result = self._build_channel().send_outbound(outbound)
        self.last_error = None if result.success else result.message
        try:
            append_notify_delivery_log(
                event_type=NOTIFY_EVENT_MANUAL_TEST,
                payload={},
                status="ok" if result.success else "failed",
                error="" if result.success else result.message,
            )
        except Exception:
            logger.exception("notify delivery log write failed")
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

    def _notify_emotion_stage_change(self, snapshot: EmotionCycleSnapshot) -> None:
        self.notify(
            NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
            dedupe_key=snapshot.stage,
            payload={
                "stage": snapshot.stage,
                "stage_label": snapshot.stage_label,
                "limit_up_count": snapshot.limit_up_count,
                "limit_down_count": snapshot.limit_down_count,
                "position_pct_max": snapshot.position_pct_max,
                "allow_new_positions": snapshot.allow_new_positions,
            },
        )

    def _notify_risk_gate_change(self, snapshot: RiskGateSnapshot) -> None:
        self.notify(
            NOTIFY_EVENT_RISK_GATE_CHANGE,
            dedupe_key=snapshot.state,
            payload={
                "state": snapshot.state,
                "state_label": snapshot.state_label,
                "warnings": list(snapshot.warnings),
                "daily_pnl_pct": snapshot.daily_pnl_pct,
                "avg_float_pnl_pct": snapshot.avg_float_pnl_pct,
            },
        )

    def _build_channel(self) -> FeishuWebhookChannel:
        url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
        secret = os.environ.get("FEISHU_WEBHOOK_SECRET", "").strip()
        return FeishuWebhookChannel(url, webhook_secret=secret)

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
