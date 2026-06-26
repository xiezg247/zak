"""板块未来展望 C（LLM）本地缓存。"""

from __future__ import annotations

import json
from typing import Any

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookDay,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRow,
)
from vnpy_ashare.storage.cache.db_session import cache_db_session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sector_flow_outlook_llm_cache (
    cache_key TEXT PRIMARY KEY,
    sector_kind TEXT NOT NULL,
    strategy_key TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL,
    forward_dates_json TEXT NOT NULL,
    rows_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def _connect():
    return cache_db_session(_SCHEMA)


def outlook_llm_cache_key(*, sector_kind: str, strategy_key: str, fingerprint: str) -> str:
    kind = str(sector_kind or "industry").strip().lower()
    key = str(strategy_key or "").strip()
    fp = str(fingerprint or "").strip()
    return f"{kind}|{key}|{fp}"


def _row_to_dict(row: SectorFlowOutlookRow) -> dict[str, Any]:
    sector = row.sector
    return {
        "sector_id": sector.sector_id,
        "sector_name": sector.name,
        "headline_pattern": row.headline_pattern,
        "rationale": row.rationale,
        "days": [{"trade_date": day.trade_date, "bias": day.bias, "strength": day.strength} for day in row.days],
    }


def _row_from_dict(payload: dict[str, Any], *, sector_lookup: dict[str, SectorFlowRow]) -> SectorFlowOutlookRow | None:
    sector_id = str(payload.get("sector_id") or "").strip()
    sector = sector_lookup.get(sector_id)
    if sector is None:
        name = str(payload.get("sector_name") or "").strip()
        if not name:
            return None
        for candidate in sector_lookup.values():
            if candidate.name == name:
                sector = candidate
                break
    if sector is None:
        return None
    days_payload = payload.get("days")
    if not isinstance(days_payload, list):
        return None
    days: list[SectorFlowOutlookDay] = []
    for item in days_payload:
        if not isinstance(item, dict):
            continue
        trade_date = str(item.get("trade_date") or "").strip()
        bias = str(item.get("bias") or "").strip()
        if not trade_date or bias not in {"偏多", "偏空", "震荡"}:
            continue
        try:
            strength = float(item.get("strength", 0.0))
        except (TypeError, ValueError):
            strength = 0.0
        days.append(
            SectorFlowOutlookDay(
                trade_date=trade_date,
                bias=bias,
                strength=max(0.0, min(1.0, round(strength, 2))),
            )
        )
    if not days:
        return None
    return SectorFlowOutlookRow(
        sector=sector,
        days=tuple(days),
        headline_pattern=str(payload.get("headline_pattern") or "").strip() or "AI情景",
        rationale=str(payload.get("rationale") or "").strip() or "基于延续A与策略B的 AI 情景参考",
        source="llm",
    )


def get_outlook_llm_cache(
    *,
    sector_kind: str,
    strategy_key: str,
    fingerprint: str,
    sector_lookup: dict[str, SectorFlowRow],
) -> SectorFlowOutlookSnapshot | None:
    key = outlook_llm_cache_key(sector_kind=sector_kind, strategy_key=strategy_key, fingerprint=fingerprint)
    now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sector_flow_outlook_llm_cache WHERE cache_key = %s AND expires_at > %s",
            (key, now),
        ).fetchone()
    if row is None:
        return None
    try:
        forward_dates = tuple(json.loads(str(row["forward_dates_json"] or "[]")))
        payload = json.loads(str(row["rows_json"] or "[]"))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, list):
        return None
    rows: list[SectorFlowOutlookRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        parsed = _row_from_dict(item, sector_lookup=sector_lookup)
        if parsed is not None:
            rows.append(parsed)
    if not rows:
        return None
    from vnpy_ashare.domain.market.sector_flow import LLM_OUTLOOK_DISCLAIMER

    return SectorFlowOutlookSnapshot(
        forward_dates=forward_dates,
        rows=tuple(rows),
        sector_kind=str(row["sector_kind"] or sector_kind),
        source="llm",
        updated_at=str(row["updated_at"] or ""),
        disclaimer=LLM_OUTLOOK_DISCLAIMER,
        data_mode="llm",
    )


def put_outlook_llm_cache(
    snapshot: SectorFlowOutlookSnapshot,
    *,
    strategy_key: str,
    fingerprint: str,
    ttl_hours: int = 24,
) -> None:
    if not snapshot.rows:
        return
    from datetime import datetime, timedelta

    key = outlook_llm_cache_key(
        sector_kind=snapshot.sector_kind,
        strategy_key=strategy_key,
        fingerprint=fingerprint,
    )
    updated_at = datetime.now()
    expires_at = updated_at + timedelta(hours=max(1, int(ttl_hours)))
    rows_json = json.dumps([_row_to_dict(row) for row in snapshot.rows], ensure_ascii=False)
    forward_dates_json = json.dumps(list(snapshot.forward_dates), ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sector_flow_outlook_llm_cache (
                cache_key, sector_kind, strategy_key, fingerprint,
                forward_dates_json, rows_json, updated_at, expires_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(cache_key) DO UPDATE SET
                forward_dates_json = excluded.forward_dates_json,
                rows_json = excluded.rows_json,
                updated_at = excluded.updated_at,
                expires_at = excluded.expires_at
            """,
            (
                key,
                snapshot.sector_kind,
                strategy_key,
                fingerprint,
                forward_dates_json,
                rows_json,
                updated_at.isoformat(timespec="seconds"),
                expires_at.isoformat(timespec="seconds"),
            ),
        )
