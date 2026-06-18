"""雷达卡片 AI 摘要本地缓存（指纹 + TTL）。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from vnpy_ashare.quotes.radar.radar_models import RadarRow
from vnpy_ashare.storage.cache.sqlite_session import sqlite_cache_session
from vnpy_common.paths import get_app_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS radar_ai_hint_cache (
    cache_key TEXT PRIMARY KEY,
    card_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    hint TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def _db_path() -> Path:
    return cast(Path, get_app_db_path().parent / "radar_ai_hint_cache.db")


def _connect(db_path: Path | None = None):
    path = db_path or _db_path()
    return sqlite_cache_session(path, _SCHEMA)


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
    with _connect() as conn:
        row = conn.execute(
            "SELECT hint FROM radar_ai_hint_cache WHERE cache_key = ? AND expires_at > ?",
            (key, now),
        ).fetchone()
    if row is None:
        return None
    return str(row["hint"] or "").strip() or None


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
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO radar_ai_hint_cache (
                cache_key, card_id, variant, fingerprint, hint, updated_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                hint = excluded.hint,
                updated_at = excluded.updated_at,
                expires_at = excluded.expires_at
            """,
            (
                key,
                card_id,
                variant,
                fingerprint,
                text,
                updated_at.isoformat(timespec="seconds"),
                expires_at.isoformat(timespec="seconds"),
            ),
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
