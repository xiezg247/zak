"""雷达卡片 AI 摘要本地缓存（指纹 + TTL）。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from vnpy_ashare.quotes.radar.radar_models import RadarRow
from vnpy_ashare.storage.repositories.cache_stores import _radar_ai_hint_repo


def rows_fingerprint(rows: tuple[RadarRow, ...]) -> str:
    parts = [f"{row.vt_symbol}:{row.metric_label}:{row.metric_value}:{row.sub_value}" for row in rows]
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return digest[:20]


def _cache_key(card_id: str, variant: str, fingerprint: str) -> str:
    return f"{card_id}:{variant}:{fingerprint}"


def get_cached_hint(
    card_id: str,
    *,
    variant: str = "",
    fingerprint: str,
) -> str | None:
    key = _cache_key(card_id, variant, fingerprint)
    now = datetime.now().isoformat(timespec="seconds")
    return _radar_ai_hint_repo.get_hint_if_fresh(key, now_text=now)


def put_cached_hint(
    card_id: str,
    *,
    variant: str = "",
    fingerprint: str,
    hint: str,
    ttl_hours: int = 24,
) -> None:
    text = str(hint or "").strip()
    if not text:
        return
    key = _cache_key(card_id, variant, fingerprint)
    updated_at = datetime.now()
    expires_at = updated_at + timedelta(hours=max(1, int(ttl_hours)))
    _radar_ai_hint_repo.upsert(
        cache_key=key,
        card_id=card_id,
        variant=variant,
        fingerprint=fingerprint,
        hint=text,
        updated_at=updated_at.isoformat(timespec="seconds"),
        expires_at=expires_at.isoformat(timespec="seconds"),
    )


def resolve_ai_hint(
    card_id: str,
    *,
    variant: str,
    fingerprint: str,
    digest: str,
    ttl_hours: int = 24,
) -> str:
    """优先读缓存；未命中则写入 digest 并返回。"""
    cached = get_cached_hint(card_id, variant=variant, fingerprint=fingerprint)
    if cached:
        return cached
    put_cached_hint(card_id, variant=variant, fingerprint=fingerprint, hint=digest, ttl_hours=ttl_hours)
    return digest
