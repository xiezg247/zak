"""定时任务上次执行状态持久化（SQLite meta）。"""

from __future__ import annotations

import json

from pydantic import Field

from vnpy_ashare.storage.connection import connect, get_meta, set_meta
from vnpy_common.domain.base import FrozenModel
from vnpy_common.storage.tables import meta

_META_PREFIX = "scheduler/job_last_run/"
_MAX_MESSAGE_LEN = 500


class JobRunMeta(FrozenModel):
    last_run_at: str = Field(description="上次执行时间（中国时区 ISO）")
    last_message: str = Field(description="上次执行摘要")
    last_success: bool | None = Field(description="上次是否成功（None 表示未知）")


def _meta_key(job_id: str) -> str:
    return f"{_META_PREFIX}{job_id}"


def load_job_run_meta(job_id: str) -> JobRunMeta | None:
    raw = get_meta(_meta_key(job_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    last_run_at = str(data.get("last_run_at") or "").strip()
    if not last_run_at:
        return None
    last_message = str(data.get("last_message") or "").strip()
    success_raw = data.get("last_success")
    if success_raw is None:
        last_success = None
    else:
        last_success = bool(success_raw)
    return JobRunMeta(
        last_run_at=last_run_at,
        last_message=last_message,
        last_success=last_success,
    )


def save_job_run_meta(
    job_id: str,
    *,
    last_run_at: str,
    last_message: str,
    last_success: bool | None,
) -> None:
    message = str(last_message or "").strip()
    if len(message) > _MAX_MESSAGE_LEN:
        message = message[: _MAX_MESSAGE_LEN - 1] + "…"
    payload = json.dumps(
        {
            "last_run_at": last_run_at,
            "last_message": message,
            "last_success": last_success,
        },
        ensure_ascii=False,
    )
    set_meta(_meta_key(job_id), payload)


def clear_job_run_meta(job_id: str) -> None:
    """测试用：清除指定任务的上次执行记录。"""
    from sqlalchemy import delete

    with connect() as conn:
        conn.execute_stmt(delete(meta).where(meta.c.key == _meta_key(job_id)))
