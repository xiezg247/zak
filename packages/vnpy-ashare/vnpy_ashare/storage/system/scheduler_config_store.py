"""定时任务配置持久化（system.scheduler_config）。"""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.storage.tables import scheduler_config as sc

_CONFIG_ID = "default"


class SchedulerConfigRepository(AppBaseRepository):
    table = sc

    def load_dict(self) -> dict[str, Any] | None:
        row = self.fetchone(select(sc.c.config_json).where(sc.c.id == _CONFIG_ID))
        if row is None:
            return None
        raw = row["config_json"]
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            return cast(dict[str, Any], json.loads(raw))
        return None

    def save_dict(self, data: dict[str, Any]) -> None:
        def _write(conn) -> None:
            stmt = pg_insert(sc).values(id=_CONFIG_ID, config_json=data, updated_at=func.now())
            stmt = stmt.on_conflict_do_update(
                index_elements=[sc.c.id],
                set_={
                    "config_json": stmt.excluded.config_json,
                    "updated_at": func.now(),
                },
            )
            conn.execute_stmt(stmt)

        self.run(_write)


_repo = SchedulerConfigRepository()


def load_scheduler_config_dict() -> dict[str, Any] | None:
    return _repo.load_dict()


def save_scheduler_config_dict(data: dict[str, Any]) -> None:
    _repo.save_dict(data)
