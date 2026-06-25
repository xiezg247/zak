"""选股方案持久化（用户保存的自定义条件）。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import Field
from sqlalchemy import select

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.domain.base import MutableModel
from vnpy_common.storage.tables import screener_schemes as ss

_SCHEME_COLUMNS = (ss.c.id, ss.c.name, ss.c.config_json, ss.c.created_at, ss.c.updated_at)


class SavedScheme(MutableModel):
    """用户保存的选股方案。"""

    id: str = Field(description="方案 id")
    name: str = Field(description="方案名称")
    config: dict[str, Any] = Field(description="方案配置")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


def _now() -> str:
    return format_china_datetime()


def _row_to_scheme(row) -> SavedScheme:
    return SavedScheme(
        id=str(row["id"]),
        name=str(row["name"]),
        config=json.loads(str(row["config_json"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class ScreenerSchemeRepository(AppUserScopedRepository):
    table = ss

    def list_schemes(self) -> list[SavedScheme]:
        rows = self.list_for_user(*_SCHEME_COLUMNS, order_by=(ss.c.updated_at.desc(),))
        return [_row_to_scheme(row) for row in rows]

    def get_scheme(self, scheme_id: str) -> SavedScheme | None:
        rows = self.list_for_user(*_SCHEME_COLUMNS, extras=(ss.c.id == scheme_id,), limit=1)
        return _row_to_scheme(rows[0]) if rows else None

    def save_scheme(self, name: str, config: dict[str, Any], *, scheme_id: str | None = None) -> SavedScheme:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("方案名称不能为空")
        now = _now()
        payload = json.dumps(config, ensure_ascii=False)
        if scheme_id:
            updated = self.update_matching(
                {"name": cleaned, "config_json": payload, "updated_at": now},
                self.scope(ss.c.id == scheme_id),
            )
            if updated == 0:
                raise RuntimeError("保存选股方案失败")
            sid = scheme_id
        else:
            sid = uuid.uuid4().hex
            self.insert_one_for_user(
                id=sid,
                name=cleaned,
                config_json=payload,
                created_at=now,
                updated_at=now,
            )
        saved = self.get_scheme(sid)
        if saved is None:
            raise RuntimeError("保存选股方案失败")
        return saved

    def delete_scheme(self, scheme_id: str) -> None:
        self.delete_matching(self.scope(ss.c.id == scheme_id))


_repo = ScreenerSchemeRepository()


def list_schemes() -> list[SavedScheme]:
    return _repo.list_schemes()


def get_scheme(scheme_id: str) -> SavedScheme | None:
    return _repo.get_scheme(scheme_id)


def save_scheme(name: str, config: dict[str, Any], *, scheme_id: str | None = None) -> SavedScheme:
    return _repo.save_scheme(name, config, scheme_id=scheme_id)


def delete_scheme(scheme_id: str) -> None:
    _repo.delete_scheme(scheme_id)
