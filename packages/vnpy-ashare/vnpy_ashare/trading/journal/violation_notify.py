"""交易流水违规 → 飞书通知。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.notifications.core.events import NOTIFY_EVENT_JOURNAL_VIOLATION

_VIOLATION_LABELS: dict[str, str] = {
    "off_plan": "计划外",
    "recession_buy": "退潮买入",
    "add_loss": "亏损加仓",
    "float_loss_hold": "浮亏扛单",
}


def format_violation_tags(tags: tuple[str, ...] | list[str]) -> str:
    parts: list[str] = []
    for tag in tags:
        key = str(tag).strip()
        if not key:
            continue
        parts.append(_VIOLATION_LABELS.get(key, key))
    return " · ".join(parts)


def publish_journal_violation(
    engine: Any,
    *,
    symbol: str,
    exchange: str,
    side: str,
    violation_tags: tuple[str, ...] | list[str],
    reason: str = "",
    emotion_stage: str = "",
    vt_symbol: str | None = None,
) -> None:
    tags = tuple(dict.fromkeys(str(item).strip() for item in violation_tags if str(item).strip()))
    if not tags:
        return
    service = getattr(engine, "notification_service", None)
    if service is None:
        return
    resolved_vt = vt_symbol or f"{symbol}.{exchange}"
    tag_key = ",".join(tags)
    service.notify(
        NOTIFY_EVENT_JOURNAL_VIOLATION,
        dedupe_key=f"{resolved_vt}:{side}:{tag_key}",
        payload={
            "vt_symbol": resolved_vt,
            "symbol": symbol,
            "exchange": exchange,
            "side": side,
            "violation_tags": format_violation_tags(tags),
            "reason": reason.strip(),
            "emotion_stage": emotion_stage.strip(),
        },
    )
