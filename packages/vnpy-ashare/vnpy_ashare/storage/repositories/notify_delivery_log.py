"""通知出站 delivery log。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from vnpy_ashare.domain.datetime import format_china_datetime
from vnpy_ashare.storage.connection import connect, init_app_db
_MAX_ROWS = 500


@dataclass(frozen=True)
class NotifyDeliveryRecord:
    id: str
    event_type: str
    channel: str
    payload_json: str
    status: str
    error: str
    created_at: str


def append_notify_delivery_log(
    *,
    event_type: str,
    channel: str = "feishu",
    payload: dict | None = None,
    status: str,
    error: str = "",
) -> str:
    init_app_db()
    record_id = uuid.uuid4().hex
    created_at = format_china_datetime()
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO notify_delivery_log(
                id, event_type, channel, payload_json, status, error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, event_type, channel, payload_json, status, error, created_at),
        )
        conn.execute(
            """
            DELETE FROM notify_delivery_log
            WHERE id NOT IN (
                SELECT id FROM notify_delivery_log
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (_MAX_ROWS,),
        )
    return record_id


def load_recent_notify_delivery_logs(*, limit: int = 20) -> list[NotifyDeliveryRecord]:
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, event_type, channel, payload_json, status, error, created_at
            FROM notify_delivery_log
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
    return [
        NotifyDeliveryRecord(
            id=str(row["id"]),
            event_type=str(row["event_type"]),
            channel=str(row["channel"]),
            payload_json=str(row["payload_json"]),
            status=str(row["status"]),
            error=str(row["error"]),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]
