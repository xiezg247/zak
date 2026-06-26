"""雷达统计/发现类卡片磁盘快照（调度预热 + UI 冷读）。"""

from __future__ import annotations

import json
from datetime import datetime

from vnpy_ashare.domain.radar.card import RadarCardData
from vnpy_ashare.domain.time.china import CHINA_TZ, DATETIME_FMT, DATETIME_MINUTE_FMT, china_now, format_china_datetime_minute
from vnpy_ashare.storage.cache.db_session import cache_db_session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS radar_card_snapshot (
    card_id TEXT NOT NULL,
    variant_key TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (card_id, variant_key)
);
"""

_DEFAULT_MAX_AGE_SEC = 120.0


def _connect():
    return cache_db_session(_SCHEMA)


def _parse_computed_at(value: str) -> datetime | None:
    text = str(value or "").strip()
    for fmt in (DATETIME_FMT, DATETIME_MINUTE_FMT):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=CHINA_TZ)
        except ValueError:
            continue
    return None


def card_snapshot_max_age_sec(card_id: str) -> float:
    if card_id == "market_emotion":
        return 60.0
    if card_id.startswith("sector_"):
        return 180.0
    return _DEFAULT_MAX_AGE_SEC


def radar_card_variant_key(card_id: str, variants: dict[str, str]) -> str:
    """与 load_radar_cards_batch 变体参数对齐的快照键。"""
    if card_id == "leader_pick":
        return str(variants.get("leader_pick_variant") or "")
    if card_id == "sector_theme":
        return str(variants.get("sector_variant") or "")
    if card_id == "sector_flow_hot":
        return str(variants.get("sector_flow_hot_variant") or "")
    if card_id == "discovery_limit_ladder":
        return str(variants.get("limit_ladder_variant") or "")
    return ""


def peek_radar_card_snapshot(
    card_id: str,
    *,
    variant_key: str = "",
    max_age_sec: float | None = None,
) -> RadarCardData | None:
    text_id = str(card_id or "").strip()
    if not text_id:
        return None
    key = str(variant_key or "")
    ttl = card_snapshot_max_age_sec(text_id) if max_age_sec is None else max_age_sec
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload_json, computed_at FROM radar_card_snapshot WHERE card_id = ? AND variant_key = ?",
            (text_id, key),
        ).fetchone()
    if row is None:
        return None
    computed = _parse_computed_at(str(row["computed_at"] or ""))
    if computed is not None and (china_now() - computed).total_seconds() > ttl:
        return None
    try:
        payload = json.loads(str(row["payload_json"] or "{}"))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return RadarCardData.model_validate(payload)
    except Exception:
        return None


def put_radar_card_snapshot(
    card_id: str,
    data: RadarCardData,
    *,
    variant_key: str = "",
    computed_at: str | None = None,
) -> None:
    text_id = str(card_id or "").strip()
    if not text_id:
        return
    key = str(variant_key or "")
    stamp = format_china_datetime_minute() if computed_at is None else computed_at
    payload = data.model_dump(mode="json")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO radar_card_snapshot (card_id, variant_key, payload_json, computed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(card_id, variant_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                computed_at = excluded.computed_at
            """,
            (text_id, key, json.dumps(payload, ensure_ascii=False), stamp),
        )


def invalidate_radar_card_snapshots() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM radar_card_snapshot")
