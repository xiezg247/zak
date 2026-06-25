"""通知出站 delivery log。"""

from __future__ import annotations

import json
import uuid

from pydantic import Field

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_common.auth.scope import user_sql
from vnpy_common.domain.base import FrozenModel

_MAX_ROWS = 500


class NotifyDeliveryRecord(FrozenModel):
    id: str = Field(description="记录主键")
    event_type: str = Field(description="事件类型")
    channel: str = Field(description="通知渠道")
    payload_json: str = Field(description="payload JSON")
    status: str = Field(description="投递状态")
    error: str = Field(description="错误信息")
    created_at: str = Field(description="创建时间")


def append_notify_delivery_log(
    *,
    event_type: str,
    channel: str = "feishu",
    payload: dict | None = None,
    status: str,
    error: str = "",
) -> str:
    init_app_db()
    uid = get_user_id()
    record_id = uuid.uuid4().hex
    created_at = format_china_datetime()
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO notify_delivery_log(
                id, user_id, event_type, channel, payload_json, status, error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, uid, event_type, channel, payload_json, status, error, created_at),
        )
        conn.execute(
            f"""
            DELETE FROM notify_delivery_log
            WHERE {user_sql()} AND id NOT IN (
                SELECT id FROM notify_delivery_log
                WHERE {user_sql()}
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (uid, uid, _MAX_ROWS),
        )
    return record_id


def load_recent_notify_delivery_logs(*, limit: int = 20) -> list[NotifyDeliveryRecord]:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, event_type, channel, payload_json, status, error, created_at
            FROM notify_delivery_log
            WHERE {user_sql()}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (uid, max(1, limit)),
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
