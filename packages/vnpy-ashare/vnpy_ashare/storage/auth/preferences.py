"""用户业务偏好（auth.user_preferences）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, TypeVar

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import connect, init_app_db

T = TypeVar("T")

_PREFERENCES_TABLE = "auth.user_preferences"


def preferences_table() -> str:
    return _PREFERENCES_TABLE


def ensure_user_preferences_schema(conn) -> None:
    _ = conn


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


def get_pref(namespace: str, key: str, default: T | None = None) -> T | Any | None:
    """读取当前用户偏好；不存在时返回 default。"""
    ns = namespace.strip()
    pref_key = key.strip()
    if not ns or not pref_key:
        return default
    init_app_db()
    uid = get_user_id()
    table = preferences_table()
    with connect() as conn:
        row = conn.execute(
            f"SELECT value_json FROM {table} WHERE user_id = ? AND namespace = ? AND key = ?",
            (uid, ns, pref_key),
        ).fetchone()
    if row is None:
        return default
    try:
        return _decode_value(row["value_json"])
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def set_pref(namespace: str, key: str, value: Any) -> None:
    """写入当前用户偏好（upsert）。"""
    ns = namespace.strip()
    pref_key = key.strip()
    if not ns or not pref_key:
        return
    init_app_db()
    uid = get_user_id()
    now = _now_iso()
    payload = _encode_value(value)
    table = preferences_table()
    with connect() as conn:
        conn.execute(
            f"""
            INSERT INTO {table} (user_id, namespace, key, value_json, updated_at)
            VALUES (?, ?, ?, ?::jsonb, ?)
            ON CONFLICT (user_id, namespace, key) DO UPDATE SET
                value_json = EXCLUDED.value_json,
                updated_at = EXCLUDED.updated_at
            """,
            (uid, ns, pref_key, payload, now),
        )


def batch_get_prefs(keys: list[tuple[str, str]]) -> dict[tuple[str, str], Any]:
    """批量读取多个用户偏好，一次 DB 查询返回全部结果。

    keys: [(namespace, key), ...]
    返回: {(namespace, key): value, ...}，不存在的 key 不在字典中。
    """
    valid: list[tuple[str, str]] = []
    for ns, pref_key in keys:
        ns_s = ns.strip()
        k_s = pref_key.strip()
        if ns_s and k_s:
            valid.append((ns_s, k_s))
    if not valid:
        return {}

    init_app_db()
    uid = get_user_id()
    table = preferences_table()
    placeholders = ",".join("(?, ?)" for _ in valid)
    flat_params: list[str] = []
    for ns, pref_key in valid:
        flat_params.append(ns)
        flat_params.append(pref_key)

    with connect() as conn:
        rows = conn.execute(
            f"SELECT namespace, key, value_json FROM {table}"
            f" WHERE user_id = ? AND (namespace, key) IN ({placeholders})",
            (uid, *flat_params),
        ).fetchall()

    result: dict[tuple[str, str], Any] = {}
    for row in rows:
        try:
            val = _decode_value(row["value_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        result[(str(row["namespace"]), str(row["key"]))] = val
    return result


def delete_pref(namespace: str, key: str) -> bool:
    init_app_db()
    uid = get_user_id()
    table = preferences_table()
    with connect() as conn:
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE user_id = ? AND namespace = ? AND key = ?",
            (uid, namespace.strip(), key.strip()),
        )
        return bool(cursor.rowcount > 0)


def delete_prefs(keys: list[tuple[str, str]]) -> int:
    """批量删除当前用户偏好，返回删除行数。"""
    valid: list[tuple[str, str]] = []
    for ns, pref_key in keys:
        ns_s = ns.strip()
        k_s = pref_key.strip()
        if ns_s and k_s:
            valid.append((ns_s, k_s))
    if not valid:
        return 0

    init_app_db()
    uid = get_user_id()
    table = preferences_table()
    placeholders = ",".join("(?, ?)" for _ in valid)
    flat_params: list[str] = []
    for ns, pref_key in valid:
        flat_params.append(ns)
        flat_params.append(pref_key)

    with connect() as conn:
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE user_id = ? AND (namespace, key) IN ({placeholders})",
            (uid, *flat_params),
        )
        return int(cursor.rowcount or 0)
