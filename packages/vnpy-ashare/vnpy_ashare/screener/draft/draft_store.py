"""待确认选股草案（内存 + TTL）。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal

from vnpy_ashare.domain.time.china import china_now, format_china_datetime
from vnpy_ashare.screener.run.runner import ScreenerRequest

DraftStatus = Literal["pending", "confirmed", "cancelled", "expired"]
Confidence = Literal["high", "medium", "low"]

DEFAULT_TTL_MINUTES = 10

_lock = threading.Lock()
_drafts: dict[str, ScreenerDraft] = {}


@dataclass
class ScreenerDraft:
    """待用户确认的选股草案（内存，带 TTL）。"""

    id: str
    natural_language: str
    request: ScreenerRequest
    summary: str
    preset_label: str
    source: str
    confidence: Confidence
    warnings: list[str]
    status: DraftStatus
    created_at: str
    expires_at: str


def _now() -> datetime:
    return china_now()


def _fmt(dt: datetime) -> str:
    return format_china_datetime(dt)


def create_draft_id() -> str:
    """生成草案 id。"""
    return uuid.uuid4().hex


def save_draft(draft: ScreenerDraft) -> None:
    """保存或覆盖草案。"""
    with _lock:
        _drafts[draft.id] = draft


def get_draft(draft_id: str) -> ScreenerDraft | None:
    """读取草案；pending 且过期时自动标记 expired。"""
    with _lock:
        draft = _drafts.get(draft_id)
        if draft is None:
            return None
        if draft.status != "pending":
            return draft
        if _now() >= datetime.strptime(draft.expires_at, "%Y-%m-%d %H:%M:%S"):
            expired = replace(draft, status="expired")
            _drafts[draft_id] = expired
            return expired
        return draft


def consume_draft(draft_id: str) -> ScreenerDraft | None:
    """pending → confirmed，单次消费；过期或已处理则返回 None。"""
    with _lock:
        draft = _drafts.get(draft_id)
        if draft is None or draft.status != "pending":
            return None
        if _now() >= datetime.strptime(draft.expires_at, "%Y-%m-%d %H:%M:%S"):
            _drafts[draft_id] = replace(draft, status="expired")
            return None
        confirmed = replace(draft, status="confirmed")
        _drafts[draft_id] = confirmed
        return confirmed


def cancel_draft(draft_id: str) -> bool:
    """取消 pending 草案；成功返回 True。"""
    with _lock:
        draft = _drafts.get(draft_id)
        if draft is None or draft.status != "pending":
            return False
        _drafts[draft_id] = replace(draft, status="cancelled")
        return True


def clear_drafts() -> None:
    """测试辅助：清空全部草案。"""
    with _lock:
        _drafts.clear()


def make_draft(
    *,
    natural_language: str,
    request: ScreenerRequest,
    summary: str,
    preset_label: str,
    source: str,
    confidence: Confidence,
    warnings: list[str],
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
) -> ScreenerDraft:
    """构造并返回 pending 草案（默认 TTL 10 分钟）。"""
    now = _now()
    return ScreenerDraft(
        id=create_draft_id(),
        natural_language=natural_language,
        request=request,
        summary=summary,
        preset_label=preset_label,
        source=source,
        confidence=confidence,
        warnings=list(warnings),
        status="pending",
        created_at=_fmt(now),
        expires_at=_fmt(now + timedelta(minutes=ttl_minutes)),
    )
