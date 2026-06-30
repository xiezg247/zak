"""雷达统计/发现类卡片磁盘快照（调度预热 + UI 冷读）。"""

from __future__ import annotations

import json
from datetime import datetime

from vnpy_ashare.domain.radar.card import RadarCardData
from vnpy_ashare.domain.time.china import CHINA_TZ, DATETIME_FMT, DATETIME_MINUTE_FMT, china_now, format_china_datetime_minute
from vnpy_ashare.storage.repositories.cache_stores import _radar_card_snapshot_repo

_DEFAULT_MAX_AGE_SEC = 120.0


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
    if card_id.startswith("watchlist_") or card_id == "position_risk":
        return 60.0
    if card_id.startswith("outlook_"):
        return 300.0
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
    if card_id in ("outlook_scenario", "outlook_predict"):
        return str(variants.get("scenario_variant") or "")
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
    row = _radar_card_snapshot_repo.get_row(text_id, key)
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
    _radar_card_snapshot_repo.upsert(
        card_id=text_id,
        variant_key=key,
        payload_json=json.dumps(payload, ensure_ascii=False),
        computed_at=stamp,
    )


def invalidate_radar_card_snapshots() -> None:
    _radar_card_snapshot_repo.clear_all()
