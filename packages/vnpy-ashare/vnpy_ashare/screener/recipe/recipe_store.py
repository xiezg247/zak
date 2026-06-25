"""多因子选股配方持久化（供定时任务引用）。"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from pydantic import Field

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.cache.db_session import app_db_session
from vnpy_common.auth.scope import user_sql
from vnpy_common.domain.base import MutableModel
from vnpy_common.storage.compat import DbRow

TriggerKind = Literal["intraday", "post_close"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS screener_recipes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    trigger_kind TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SavedRecipe(MutableModel):
    """用户保存的多因子选股配方。"""

    id: str = Field(description="配方 id")
    name: str = Field(description="配方名称")
    trigger_kind: TriggerKind = Field(description="触发类型（盘中/盘后）")
    config: dict[str, Any] = Field(description="配方配置")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


def _connect():
    return app_db_session(_SCHEMA)


def _now() -> str:
    return format_china_datetime()


def list_saved_recipes(*, trigger_kind: TriggerKind | None = None) -> list[SavedRecipe]:
    """列出用户配方；可按 trigger_kind 过滤。"""
    uid = get_user_id()
    with _connect() as conn:
        if trigger_kind:
            rows = conn.execute(
                f"""
                SELECT id, name, trigger_kind, config_json, created_at, updated_at
                FROM screener_recipes
                WHERE {user_sql('trigger_kind=?')}
                ORDER BY updated_at DESC
                """,
                (uid, trigger_kind),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT id, name, trigger_kind, config_json, created_at, updated_at
                FROM screener_recipes
                WHERE {user_sql()}
                ORDER BY updated_at DESC
                """,
                (uid,),
            ).fetchall()
    return [_row_to_saved(row) for row in rows]


def get_saved_recipe(recipe_id: str) -> SavedRecipe | None:
    """按 id 读取用户配方。"""
    uid = get_user_id()
    with _connect() as conn:
        row = conn.execute(
            f"""
            SELECT id, name, trigger_kind, config_json, created_at, updated_at
            FROM screener_recipes WHERE {user_sql('id=?')}
            """,
            (uid, recipe_id),
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
    uid = get_user_id()
    with _connect() as conn:
        if recipe_id:
            conn.execute(
                f"""
                UPDATE screener_recipes
                SET name=?, trigger_kind=?, config_json=?, updated_at=?
                WHERE {user_sql('id=?')}
                """,
                (cleaned, trigger_kind, payload, now, uid, recipe_id),
            )
            sid = recipe_id
        else:
            sid = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO screener_recipes
                (id, user_id, name, trigger_kind, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, uid, cleaned, trigger_kind, payload, now, now),
            )
    saved = get_saved_recipe(sid)
    if saved is None:
        raise RuntimeError("保存选股配方失败")
    return saved


def delete_recipe(recipe_id: str) -> bool:
    """删除用户配方；成功返回 True。"""
    uid = get_user_id()
    with _connect() as conn:
        cursor = conn.execute(f"DELETE FROM screener_recipes WHERE {user_sql('id=?')}", (uid, recipe_id))
        return bool(cursor.rowcount > 0)


def _row_to_saved(row: DbRow) -> SavedRecipe:
    return SavedRecipe(
        id=str(row["id"]),
        name=str(row["name"]),
        trigger_kind=str(row["trigger_kind"]),  # type: ignore[arg-type]
        config=json.loads(str(row["config_json"] or "{}")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
