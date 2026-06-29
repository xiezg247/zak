"""auth.user_preferences repository。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_common.storage.repository import BaseRepository
from vnpy_common.storage.tables.auth import user_preferences as up


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _decode_value(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list, bool, int, float)):
        return raw
    text = str(raw)
    if not text:
        return None
    return json.loads(text)


def _encode_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


class UserPreferencesRepository(BaseRepository):
    table = up

    def get(self, *, user_id: str, namespace: str, key: str) -> Any | None:
        row = self.fetchone(
            select(up.c.value_json).where(
                up.c.user_id == user_id,
                up.c.namespace == namespace,
                up.c.key == key,
            )
        )
        if row is None:
            return None
        try:
            return _decode_value(row["value_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def set(self, *, user_id: str, namespace: str, key: str, value: Any) -> None:
        now = _now_iso()
        payload = _encode_value(value)

        def _write(conn) -> None:
            stmt = pg_insert(up).values(
                user_id=user_id,
                namespace=namespace,
                key=key,
                value_json=payload,
                updated_at=now,
            )
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[up.c.user_id, up.c.namespace, up.c.key],
                    set_={"value_json": excluded.value_json, "updated_at": excluded.updated_at},
                )
            )

        self.run(_write)

    def batch_get(self, *, user_id: str, keys: list[tuple[str, str]]) -> dict[tuple[str, str], Any]:
        valid = [(ns.strip(), k.strip()) for ns, k in keys if ns.strip() and k.strip()]
        if not valid:
            return {}
        rows = self.fetchall(
            select(up.c.namespace, up.c.key, up.c.value_json).where(
                up.c.user_id == user_id,
                tuple_(up.c.namespace, up.c.key).in_(valid),
            )
        )
        result: dict[tuple[str, str], Any] = {}
        for row in rows:
            try:
                val = _decode_value(row["value_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            result[(str(row["namespace"]), str(row["key"]))] = val
        return result

    def delete_one(self, *, user_id: str, namespace: str, key: str) -> bool:
        with self.session() as conn:
            cursor = conn.execute_stmt(
                delete(up).where(
                    up.c.user_id == user_id,
                    up.c.namespace == namespace.strip(),
                    up.c.key == key.strip(),
                )
            )
            return bool(cursor.rowcount > 0)

    def delete_many(self, *, user_id: str, keys: list[tuple[str, str]]) -> int:
        valid = [(ns.strip(), k.strip()) for ns, k in keys if ns.strip() and k.strip()]
        if not valid:
            return 0
        with self.session() as conn:
            cursor = conn.execute_stmt(
                delete(up).where(
                    up.c.user_id == user_id,
                    tuple_(up.c.namespace, up.c.key).in_(valid),
                )
            )
            return int(cursor.rowcount or 0)

    def delete_for_user_ids(self, conn, user_ids: list[str]) -> None:
        if not user_ids:
            return
        conn.execute_stmt(delete(up).where(up.c.user_id.in_(user_ids)))


_prefs_repo = UserPreferencesRepository()


def get_pref(namespace: str, key: str, default: Any | None = None) -> Any | None:
    ns = namespace.strip()
    pref_key = key.strip()
    if not ns or not pref_key:
        return default
    value = _prefs_repo.get(user_id=get_user_id(), namespace=ns, key=pref_key)
    return default if value is None else value


def set_pref(namespace: str, key: str, value: Any) -> None:
    ns = namespace.strip()
    pref_key = key.strip()
    if not ns or not pref_key:
        return
    _prefs_repo.set(user_id=get_user_id(), namespace=ns, key=pref_key, value=value)


def batch_get_prefs(keys: list[tuple[str, str]]) -> dict[tuple[str, str], Any]:
    return _prefs_repo.batch_get(user_id=get_user_id(), keys=keys)


def delete_pref(namespace: str, key: str) -> bool:
    return _prefs_repo.delete_one(user_id=get_user_id(), namespace=namespace, key=key)


def delete_prefs(keys: list[tuple[str, str]]) -> int:
    return _prefs_repo.delete_many(user_id=get_user_id(), keys=keys)
