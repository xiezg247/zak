"""多因子选股配方持久化（供定时任务引用）。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from vnpy_ashare.paths import get_app_db_path

TriggerKind = Literal["intraday", "post_close"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS screener_recipes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    trigger_kind TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass
class SavedRecipe:
    """用户保存的多因子选股配方。"""

    id: str
    name: str
    trigger_kind: TriggerKind
    config: dict[str, Any]
    created_at: str
    updated_at: str


@contextmanager
def _connect():
    path = get_app_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_saved_recipes(*, trigger_kind: TriggerKind | None = None) -> list[SavedRecipe]:
    """列出用户配方；可按 trigger_kind 过滤。"""
    with _connect() as conn:
        if trigger_kind:
            rows = conn.execute(
                """
                SELECT id, name, trigger_kind, config_json, created_at, updated_at
                FROM screener_recipes
                WHERE trigger_kind=?
                ORDER BY updated_at DESC
                """,
                (trigger_kind,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, trigger_kind, config_json, created_at, updated_at
                FROM screener_recipes
                ORDER BY updated_at DESC
                """
            ).fetchall()
    return [_row_to_saved(row) for row in rows]


def get_saved_recipe(recipe_id: str) -> SavedRecipe | None:
    """按 id 读取用户配方。"""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, trigger_kind, config_json, created_at, updated_at
            FROM screener_recipes WHERE id=?
            """,
            (recipe_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_saved(row)


def save_recipe(
    name: str,
    *,
    trigger_kind: TriggerKind,
    config: dict[str, Any],
    recipe_id: str | None = None,
) -> SavedRecipe:
    """新建或更新用户配方。"""
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("配方名称不能为空")
    now = _now()
    payload = json.dumps(config, ensure_ascii=False)
    with _connect() as conn:
        if recipe_id:
            conn.execute(
                """
                UPDATE screener_recipes
                SET name=?, trigger_kind=?, config_json=?, updated_at=?
                WHERE id=?
                """,
                (cleaned, trigger_kind, payload, now, recipe_id),
            )
            sid = recipe_id
        else:
            sid = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO screener_recipes
                (id, name, trigger_kind, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sid, cleaned, trigger_kind, payload, now, now),
            )
    saved = get_saved_recipe(sid)
    if saved is None:
        raise RuntimeError("保存选股配方失败")
    return saved


def delete_recipe(recipe_id: str) -> bool:
    """删除用户配方；成功返回 True。"""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM screener_recipes WHERE id=?", (recipe_id,))
        return cursor.rowcount > 0


def _row_to_saved(row: sqlite3.Row) -> SavedRecipe:
    return SavedRecipe(
        id=str(row["id"]),
        name=str(row["name"]),
        trigger_kind=str(row["trigger_kind"]),  # type: ignore[arg-type]
        config=json.loads(str(row["config_json"] or "{}")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
