"""待确认配方草案（内存 + TTL）。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from vnpy_ashare.screener.recipe.recipe import TriggerKind

DraftStatus = Literal["pending", "confirmed", "cancelled", "expired"]
Confidence = Literal["high", "medium", "low"]

DEFAULT_TTL_MINUTES = 10

_lock = threading.Lock()
_drafts: dict[str, RecipeDraft] = {}


@dataclass
class RecipeDraft:
    """待用户确认的配方草案（内存，带 TTL）。"""

    id: str
    natural_language: str
    recipe_id: str
    trigger_kind: TriggerKind
    top_n: int
    summary: str
    confidence: Confidence
    warnings: list[str]
    status: DraftStatus
    created_at: str
    expires_at: str


def _now() -> datetime:
    return datetime.now()


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


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
            expired = replace(draft, status="expired")
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
            _drafts[draft_id] = replace(draft, status="expired")
            return None
        confirmed = replace(draft, status="confirmed")
        _drafts[draft_id] = confirmed
        return confirmed


def cancel_recipe_draft(draft_id: str) -> bool:
    with _lock:
        draft = _drafts.get(draft_id)
        if draft is None or draft.status != "pending":
            return False
        _drafts[draft_id] = replace(draft, status="cancelled")
        return True
