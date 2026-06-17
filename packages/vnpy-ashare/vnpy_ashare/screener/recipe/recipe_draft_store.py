"""待确认配方草案（内存 + TTL）。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.domain.time.china import china_now, format_china_datetime
from vnpy_ashare.screener.recipe.recipe import TriggerKind

DraftStatus = Literal["pending", "confirmed", "cancelled", "expired"]
Confidence = Literal["high", "medium", "low"]

DEFAULT_TTL_MINUTES = 10

_lock = threading.Lock()
_drafts: dict[str, RecipeDraft] = {}


class RecipeDraft(MutableModel):
    """待用户确认的配方草案（内存，带 TTL）。"""

    id: str = Field(description="草案 id")
    natural_language: str = Field(description="用户原始自然语言")
    recipe_id: str = Field(description="配方 id")
    trigger_kind: TriggerKind = Field(description="触发类型（盘中/盘后）")
    top_n: int = Field(description="返回条数上限")
    summary: str = Field(description="人类可读摘要")
    confidence: Confidence = Field(description="解析置信度")
    warnings: list[str] = Field(description="警告信息列表")
    status: DraftStatus = Field(description="草案状态")
    created_at: str = Field(description="创建时间")
    expires_at: str = Field(description="过期时间")


def _now() -> datetime:
    return china_now()


def _fmt(dt: datetime) -> str:
    return format_china_datetime(dt)


def create_draft_id() -> str:
    return uuid.uuid4().hex


def save_recipe_draft(draft: RecipeDraft) -> None:
    with _lock:
        _drafts[draft.id] = draft


def get_recipe_draft(draft_id: str) -> RecipeDraft | None:
    with _lock:
        draft = _drafts.get(draft_id)
        if draft is None:
            return None
        if draft.status != "pending":
            return draft
        if _now() >= datetime.strptime(draft.expires_at, "%Y-%m-%d %H:%M:%S"):
            expired = draft.model_copy(update={"status": "expired"})
            _drafts[draft_id] = expired
            return expired
        return draft


def consume_recipe_draft(draft_id: str) -> RecipeDraft | None:
    """pending → confirmed，单次消费。"""
    with _lock:
        draft = _drafts.get(draft_id)
        if draft is None or draft.status != "pending":
            return None
        if _now() >= datetime.strptime(draft.expires_at, "%Y-%m-%d %H:%M:%S"):
            _drafts[draft_id] = draft.model_copy(update={"status": "expired"})
            return None
        confirmed = draft.model_copy(update={"status": "confirmed"})
        _drafts[draft_id] = confirmed
        return confirmed


def cancel_recipe_draft(draft_id: str) -> bool:
    with _lock:
        draft = _drafts.get(draft_id)
        if draft is None or draft.status != "pending":
            return False
        _drafts[draft_id] = draft.model_copy(update={"status": "cancelled"})
        return True
