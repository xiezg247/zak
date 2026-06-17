"""通知消息正文模板。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from vnpy_ashare.notifications.events import (
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
)

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _now_text() -> str:
    return datetime.now(_SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


def format_notify_text(event_id: str, payload: dict[str, Any]) -> str:
    now = _now_text()
    if event_id == NOTIFY_EVENT_MANUAL_TEST:
        return f"【zak】测试消息\n飞书 Webhook 配置正常\n时间 {now}"

    if event_id == NOTIFY_EVENT_SCREENER_INTRADAY_DONE:
        return _format_screener_done("盘中选股完成", payload, now)

    if event_id == NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE:
        return _format_screener_done("盘后选股完成", payload, now)

    if event_id == NOTIFY_EVENT_SCHEDULER_JOB_FAILED:
        job_name = str(payload.get("job_name") or payload.get("job_id") or "未知任务")
        job_id = str(payload.get("job_id") or "")
        message = str(payload.get("message") or "").strip()
        lines = [f"【zak】定时任务失败", f"任务 {job_name}"]
        if job_id and job_id != job_name:
            lines.append(f"ID {job_id}")
        if message:
            lines.append(message)
        lines.append(f"时间 {now}")
        return "\n".join(lines)

    msg = f"unknown event: {event_id}"
    raise ValueError(msg)


def _format_screener_done(title: str, payload: dict[str, Any], now: str) -> str:
    message = str(payload.get("message") or "").strip()
    recipe = str(payload.get("recipe") or "").strip()
    hit_count = payload.get("hit_count")
    lines = [f"【zak】{title}"]
    if recipe:
        lines.append(f"配方 {recipe}")
    if hit_count is not None:
        lines.append(f"命中 {hit_count} 条")
    if message:
        lines.append(message)
    lines.append(f"时间 {now}")
    lines.append("打开客户端查看选股 Hub 运行历史")
    return "\n".join(lines)
