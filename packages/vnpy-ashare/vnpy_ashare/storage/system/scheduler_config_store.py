"""定时任务配置持久化（system.scheduler_config）。"""

from __future__ import annotations

import json
from typing import Any

from vnpy_ashare.storage.connection import connect, init_app_db

_CONFIG_ID = "default"


def load_scheduler_config_dict() -> dict[str, Any] | None:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT config_json FROM scheduler_config WHERE id = ?",
            (_CONFIG_ID,),
        ).fetchone()
    if row is None:
        return None
    raw = row["config_json"]
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return None


def save_scheduler_config_dict(data: dict[str, Any]) -> None:
    init_app_db()
    payload = json.dumps(data, ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO scheduler_config (id, config_json, updated_at)
            VALUES (?, ?::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET
                config_json = EXCLUDED.config_json,
                updated_at = EXCLUDED.updated_at
            """,
            (_CONFIG_ID, payload),
        )
