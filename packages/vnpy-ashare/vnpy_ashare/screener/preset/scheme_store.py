"""选股方案持久化（用户保存的自定义条件）。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_common.paths import get_app_db_path

_SCHEME_SCHEMA = """
CREATE TABLE IF NOT EXISTS screener_schemes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SavedScheme(MutableModel):
    """用户保存的选股方案。"""

    id: str = Field(description="方案 id")
    name: str = Field(description="方案名称")
    config: dict[str, Any] = Field(description="方案配置")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


@contextmanager
def _connect():
    path = get_app_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEME_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return format_china_datetime()


def list_schemes() -> list[SavedScheme]:
    """列出全部方案，按更新时间倒序。"""
    with _connect() as conn:
        rows = conn.execute("SELECT id, name, config_json, created_at, updated_at FROM screener_schemes ORDER BY updated_at DESC").fetchall()
    result: list[SavedScheme] = []
    for row in rows:
        result.append(
            SavedScheme(
                id=str(row["id"]),
                name=str(row["name"]),
                config=json.loads(str(row["config_json"])),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
        )
    return result


def get_scheme(scheme_id: str) -> SavedScheme | None:
    """按 id 读取方案。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, config_json, created_at, updated_at FROM screener_schemes WHERE id=?",
            (scheme_id,),
        ).fetchone()
    if row is None:
        return None
    return SavedScheme(
        id=str(row["id"]),
        name=str(row["name"]),
        config=json.loads(str(row["config_json"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def save_scheme(name: str, config: dict[str, Any], *, scheme_id: str | None = None) -> SavedScheme:
    """新建或更新方案；``scheme_id`` 非空时为更新。"""
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("方案名称不能为空")
    now = _now()
    payload = json.dumps(config, ensure_ascii=False)
    with _connect() as conn:
        if scheme_id:
            conn.execute(
                "UPDATE screener_schemes SET name=?, config_json=?, updated_at=? WHERE id=?",
                (cleaned, payload, now, scheme_id),
            )
            sid = scheme_id
        else:
            sid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO screener_schemes (id, name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (sid, cleaned, payload, now, now),
            )
    saved = get_scheme(sid)
    if saved is None:
        raise RuntimeError("保存选股方案失败")
    return saved


def delete_scheme(scheme_id: str) -> None:
    """删除方案。"""
    with _connect() as conn:
        conn.execute("DELETE FROM screener_schemes WHERE id=?", (scheme_id,))
