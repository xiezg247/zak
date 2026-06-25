"""通知出站 delivery log。"""

from __future__ import annotations

import json
import uuid

from pydantic import Field
from sqlalchemy import delete, select

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.domain.base import FrozenModel
from vnpy_common.storage.tables import notify_delivery_log as ndl

_MAX_ROWS = 500

_LOG_COLUMNS = (
    ndl.c.id,
    ndl.c.event_type,
    ndl.c.channel,
    ndl.c.payload_json,
    ndl.c.status,
    ndl.c.error,
    ndl.c.created_at,
)


class NotifyDeliveryRecord(FrozenModel):
    id: str = Field(description="记录主键")
    event_type: str = Field(description="事件类型")
    channel: str = Field(description="通知渠道")
    payload_json: str = Field(description="payload JSON")
    status: str = Field(description="投递状态")
    error: str = Field(description="错误信息")
    created_at: str = Field(description="创建时间")


class NotifyDeliveryLogRepository(AppUserScopedRepository):
    table = ndl

    def append(
        self,
        *,
        event_type: str,
        channel: str = "feishu",
        payload: dict | None = None,
        status: str,
        error: str = "",
    ) -> str:
        record_id = uuid.uuid4().hex
        created_at = format_china_datetime()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)

        def _write(conn) -> None:
            self.insert_for_user(
                conn,
                id=record_id,
                event_type=event_type,
                channel=channel,
                payload_json=payload_json,
                status=status,
                error=error,
                created_at=created_at,
            )
            keep_ids = select(ndl.c.id).where(self.scope()).order_by(ndl.c.created_at.desc()).limit(_MAX_ROWS)
            conn.execute_stmt(delete(ndl).where(self.scope(), ndl.c.id.not_in(keep_ids)))

        self.run(_write)
        return record_id

    def load_recent(self, *, limit: int = 20) -> list[NotifyDeliveryRecord]:
        rows = self.list_for_user(
            *_LOG_COLUMNS,
            order_by=(ndl.c.created_at.desc(),),
            limit=max(1, limit),
        )
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


_repo = NotifyDeliveryLogRepository()


def append_notify_delivery_log(
    *,
    event_type: str,
    channel: str = "feishu",
    payload: dict | None = None,
    status: str,
    error: str = "",
) -> str:
    return _repo.append(
        event_type=event_type,
        channel=channel,
        payload=payload,
        status=status,
        error=error,
    )


def load_recent_notify_delivery_logs(*, limit: int = 20) -> list[NotifyDeliveryRecord]:
    return _repo.load_recent(limit=limit)
