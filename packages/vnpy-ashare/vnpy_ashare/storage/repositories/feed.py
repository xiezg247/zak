"""信息流 repository（PostgreSQL app schema）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.domain.feed.models import (
    FEED_RETENTION_DAYS,
    SOURCE_TYPE_BILIBILI_UP,
    FeedItem,
    FeedItemDraft,
    FeedSubscription,
    FeedSubscriptionConfig,
)
from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_common.auth.scope import user_sql

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feed_subscriptions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT '',
    source_type     TEXT NOT NULL DEFAULT 'bilibili_up',
    source_id       TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    avatar_url      TEXT NOT NULL DEFAULT '',
    config_json     TEXT NOT NULL DEFAULT '{}',
    enabled         INTEGER NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(source_type, source_id)
);

CREATE TABLE IF NOT EXISTS feed_items (
    id              TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    item_type       TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    summary         TEXT NOT NULL DEFAULT '',
    url             TEXT NOT NULL,
    author_name     TEXT NOT NULL DEFAULT '',
    published_at    TEXT NOT NULL,
    payload_json    TEXT NOT NULL DEFAULT '{}',
    read_at         TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(source_type, external_id)
);
CREATE INDEX IF NOT EXISTS idx_feed_items_published ON feed_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_feed_items_sub ON feed_items(subscription_id, published_at DESC);

CREATE TABLE IF NOT EXISTS feed_cursors (
    subscription_id TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT '',
    last_video_ts   INTEGER NOT NULL DEFAULT 0,
    last_dynamic_id TEXT NOT NULL DEFAULT '',
    last_ok_at      TEXT,
    last_error      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS feed_item_reads (
    user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    read_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
"""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_schema() -> None:
    init_app_db()
    with connect() as conn:
        conn.executescript(_SCHEMA)


def _row_to_subscription(row: Any) -> FeedSubscription:
    config_raw = json.loads(row["config_json"] or "{}")
    config_raw.pop("videos", None)
    return FeedSubscription(
        id=row["id"],
        source_type=row["source_type"],
        source_id=row["source_id"],
        display_name=row["display_name"] or "",
        avatar_url=row["avatar_url"] or "",
        config=FeedSubscriptionConfig.model_validate(config_raw),
        enabled=bool(row["enabled"]),
        sort_order=int(row["sort_order"] or 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_item(row: Any) -> FeedItem:
    read_at = None
    if "user_read_at" in row.keys():
        read_at = row["user_read_at"]
    elif "read_at" in row.keys():
        read_at = row["read_at"]
    return FeedItem(
        id=row["id"],
        subscription_id=row["subscription_id"],
        source_type=row["source_type"],
        external_id=row["external_id"],
        item_type=row["item_type"],
        title=row["title"] or "",
        summary=row["summary"] or "",
        url=row["url"],
        author_name=row["author_name"] or "",
        published_at=row["published_at"],
        payload=json.loads(row["payload_json"] or "{}"),
        read_at=read_at,
        created_at=row["created_at"],
    )


def _items_base_sql() -> str:
    return """
        SELECT fi.*, fir.read_at AS user_read_at
        FROM feed_items fi
        INNER JOIN feed_subscriptions fs ON fs.id = fi.subscription_id AND fs.user_id = ?
        LEFT JOIN feed_item_reads fir ON fir.item_id = fi.id AND fir.user_id = ?
    """


def count_subscriptions() -> int:
    _ensure_schema()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(f"SELECT COUNT(*) AS c FROM feed_subscriptions WHERE {user_sql()}", (uid,)).fetchone()
    return int(row["c"] if row else 0)


def list_subscriptions(*, enabled_only: bool = False) -> list[FeedSubscription]:
    _ensure_schema()
    uid = get_user_id()
    sql = f"SELECT * FROM feed_subscriptions WHERE {user_sql()}"
    params: list[Any] = [uid]
    if enabled_only:
        sql += " AND enabled = 1"
    sql += " ORDER BY sort_order ASC, created_at ASC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_subscription(row) for row in rows]


def get_subscription(subscription_id: str) -> FeedSubscription | None:
    _ensure_schema()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"SELECT * FROM feed_subscriptions WHERE {user_sql('id = ?')}",
            (uid, subscription_id),
        ).fetchone()
    return _row_to_subscription(row) if row is not None else None


def find_subscription_by_source(source_type: str, source_id: str) -> FeedSubscription | None:
    _ensure_schema()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"SELECT * FROM feed_subscriptions WHERE {user_sql('source_type = ? AND source_id = ?')}",
            (uid, source_type, source_id),
        ).fetchone()
    return _row_to_subscription(row) if row is not None else None


def insert_subscription(
    *,
    source_type: str,
    source_id: str,
    display_name: str,
    avatar_url: str = "",
    config: FeedSubscriptionConfig | None = None,
) -> FeedSubscription:
    _ensure_schema()
    uid = get_user_id()
    now = _now_iso()
    sub_id = str(uuid.uuid4())
    cfg = config or FeedSubscriptionConfig()
    with connect() as conn:
        row = conn.execute(f"SELECT COALESCE(MAX(sort_order), -1) AS m FROM feed_subscriptions WHERE {user_sql()}", (uid,)).fetchone()
        sort_order = int(row["m"] if row else -1) + 1
        conn.execute(
            "INSERT INTO feed_subscriptions("
            "id, user_id, source_type, source_id, display_name, avatar_url, config_json, enabled, sort_order, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (
                sub_id,
                uid,
                source_type,
                source_id,
                display_name,
                avatar_url,
                json.dumps(cfg.model_dump(), ensure_ascii=False),
                sort_order,
                now,
                now,
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO feed_cursors(subscription_id, user_id, last_video_ts, last_dynamic_id, last_error) VALUES (?, ?, 0, '', '')",
            (sub_id, uid),
        )
    sub = get_subscription(sub_id)
    assert sub is not None
    return sub


def update_subscription(
    subscription_id: str,
    *,
    display_name: str | None = None,
    avatar_url: str | None = None,
    config: FeedSubscriptionConfig | None = None,
    enabled: bool | None = None,
) -> None:
    _ensure_schema()
    uid = get_user_id()
    fields: list[str] = []
    values: list[Any] = []
    if display_name is not None:
        fields.append("display_name = ?")
        values.append(display_name)
    if avatar_url is not None:
        fields.append("avatar_url = ?")
        values.append(avatar_url)
    if config is not None:
        fields.append("config_json = ?")
        values.append(json.dumps(config.model_dump(), ensure_ascii=False))
    if enabled is not None:
        fields.append("enabled = ?")
        values.append(1 if enabled else 0)
    if not fields:
        return
    fields.append("updated_at = ?")
    values.append(_now_iso())
    values.extend([uid, subscription_id])
    with connect() as conn:
        conn.execute(
            f"UPDATE feed_subscriptions SET {', '.join(fields)} WHERE {user_sql('id = ?')}",
            values,
        )


def delete_subscription(subscription_id: str) -> None:
    _ensure_schema()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(
            f"DELETE FROM feed_cursors WHERE subscription_id = ? AND {user_sql()}",
            (subscription_id, uid),
        )
        conn.execute(
            f"DELETE FROM feed_subscriptions WHERE {user_sql('id = ?')}",
            (uid, subscription_id),
        )


def get_cursor(subscription_id: str) -> dict[str, Any]:
    _ensure_schema()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"SELECT last_video_ts, last_dynamic_id, last_ok_at, last_error FROM feed_cursors WHERE subscription_id = ? AND {user_sql()}",
            (subscription_id, uid),
        ).fetchone()
    if row is None:
        return {
            "last_video_ts": 0,
            "last_dynamic_id": "",
            "last_ok_at": "",
            "last_error": "",
        }
    return {
        "last_video_ts": int(row["last_video_ts"] or 0),
        "last_dynamic_id": str(row["last_dynamic_id"] or ""),
        "last_ok_at": str(row["last_ok_at"] or ""),
        "last_error": str(row["last_error"] or ""),
    }


def update_cursor(
    subscription_id: str,
    *,
    last_video_ts: int | None = None,
    last_dynamic_id: str | None = None,
    last_ok_at: str | None = None,
    last_error: str | None = None,
) -> None:
    _ensure_schema()
    uid = get_user_id()
    cursor = get_cursor(subscription_id)
    with connect() as conn:
        conn.execute(
            "INSERT INTO feed_cursors(subscription_id, user_id, last_video_ts, last_dynamic_id, last_ok_at, last_error) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(subscription_id) DO UPDATE SET "
            "last_video_ts = excluded.last_video_ts, "
            "last_dynamic_id = excluded.last_dynamic_id, "
            "last_ok_at = excluded.last_ok_at, "
            "last_error = excluded.last_error",
            (
                subscription_id,
                uid,
                int(last_video_ts if last_video_ts is not None else cursor["last_video_ts"]),
                str(last_dynamic_id if last_dynamic_id is not None else cursor["last_dynamic_id"]),
                last_ok_at if last_ok_at is not None else cursor["last_ok_at"],
                last_error if last_error is not None else cursor["last_error"],
            ),
        )


def insert_items_if_new(
    subscription_id: str,
    source_type: str,
    drafts: list[FeedItemDraft],
) -> list[FeedItem]:
    """批量插入新条目（ON CONFLICT DO NOTHING），一次性返回新插入的条目。"""
    if not drafts:
        return []
    _ensure_schema()
    now = _now_iso()
    item_ids = [str(uuid.uuid4()) for _ in drafts]
    batch = [
        (
            item_ids[i],
            subscription_id,
            source_type,
            draft.external_id,
            draft.item_type,
            draft.title,
            draft.summary,
            draft.url,
            draft.author_name,
            draft.published_at,
            json.dumps(draft.payload, ensure_ascii=False),
            now,
        )
        for i, draft in enumerate(drafts)
    ]
    inserted: list[FeedItem] = []
    with connect() as conn:
        conn.executemany(
            "INSERT INTO feed_items("
            "id, subscription_id, source_type, external_id, item_type, title, summary, url, "
            "author_name, published_at, payload_json, read_at, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?) "
            "ON CONFLICT(source_type, external_id) DO NOTHING",
            batch,
        )
        # 批量回查新插入项
        ext_ids = [d.external_id for d in drafts]
        placeholders = ",".join("?" for _ in ext_ids)
        rows = conn.execute(
            f"SELECT * FROM feed_items WHERE source_type = ? AND external_id IN ({placeholders}) AND created_at = ?",
            (source_type, *ext_ids, now),
        ).fetchall()
        inserted.extend(_row_to_item(row) for row in rows)
    return inserted


def upsert_items(
    subscription_id: str,
    source_type: str,
    drafts: list[FeedItemDraft],
) -> list[FeedItem]:
    """批量插入或更新条目（保留用户已读状态）；返回本次新插入的条目。"""
    if not drafts:
        return []
    _ensure_schema()
    now = _now_iso()

    with connect() as conn:
        # 批量查询已有条目
        ext_ids = [d.external_id for d in drafts]
        placeholders = ",".join("?" for _ in ext_ids)
        existing_rows = conn.execute(
            f"SELECT id, external_id FROM feed_items WHERE source_type = ? AND external_id IN ({placeholders})",
            (source_type, *ext_ids),
        ).fetchall()
        existing_map: dict[str, str] = {str(r["external_id"]): str(r["id"]) for r in existing_rows}

        # 更新已有
        update_batch = []
        for draft in drafts:
            if draft.external_id in existing_map:
                update_batch.append((
                    draft.item_type, draft.title, draft.summary, draft.url,
                    draft.author_name, draft.published_at,
                    json.dumps(draft.payload, ensure_ascii=False),
                    existing_map[draft.external_id],
                ))
        if update_batch:
            conn.executemany(
                "UPDATE feed_items SET item_type = ?, title = ?, summary = ?, url = ?, "
                "author_name = ?, published_at = ?, payload_json = ? WHERE id = ?",
                update_batch,
            )

        # 插入新条目
        new_drafts = [d for d in drafts if d.external_id not in existing_map]
        if not new_drafts:
            return []

        item_ids = [str(uuid.uuid4()) for _ in new_drafts]
        insert_batch = [
            (
                item_ids[i], subscription_id, source_type,
                draft.external_id, draft.item_type, draft.title, draft.summary,
                draft.url, draft.author_name, draft.published_at,
                json.dumps(draft.payload, ensure_ascii=False), now,
            )
            for i, draft in enumerate(new_drafts)
        ]
        conn.executemany(
            "INSERT INTO feed_items(id, subscription_id, source_type, external_id, "
            "item_type, title, summary, url, author_name, published_at, "
            "payload_json, read_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
            insert_batch,
        )

        # 回查新插入项
        new_ext_ids = [d.external_id for d in new_drafts]
        new_placeholders = ",".join("?" for _ in new_ext_ids)
        rows = conn.execute(
            f"SELECT * FROM feed_items WHERE source_type = ? AND external_id IN ({new_placeholders}) AND created_at = ?",
            (source_type, *new_ext_ids, now),
        ).fetchall()
        return [_row_to_item(row) for row in rows]


def list_items(
    *,
    limit: int = 50,
    unread_only: bool = False,
    subscription_id: str | None = None,
) -> list[FeedItem]:
    _ensure_schema()
    uid = get_user_id()
    limit = max(1, min(int(limit), 200))
    clauses: list[str] = []
    params: list[Any] = [uid, uid]
    if unread_only:
        clauses.append("fir.read_at IS NULL")
    if subscription_id:
        clauses.append("fi.subscription_id = ?")
        params.append(subscription_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"{_items_base_sql()} {where} ORDER BY fi.published_at DESC, fi.created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [_row_to_item(row) for row in rows]


def count_unread(*, subscription_id: str | None = None) -> int:
    _ensure_schema()
    uid = get_user_id()
    clauses = ["fir.read_at IS NULL"]
    params: list[Any] = [uid, uid]
    if subscription_id:
        clauses.append("fi.subscription_id = ?")
        params.append(subscription_id)
    where = " AND ".join(clauses)
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM feed_items fi
            INNER JOIN feed_subscriptions fs ON fs.id = fi.subscription_id AND fs.user_id = ?
            LEFT JOIN feed_item_reads fir ON fir.item_id = fi.id AND fir.user_id = ?
            WHERE {where}
            """,
            params,
        ).fetchone()
    return int(row["c"] if row else 0)


def mark_read(item_ids: list[str]) -> None:
    """批量标记已读 —— 一次 executemany 代替 N 次 execute。"""
    if not item_ids:
        return
    _ensure_schema()
    uid = get_user_id()
    now = _now_iso()
    batch = [(uid, item_id, now) for item_id in item_ids]
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO feed_item_reads (user_id, item_id, read_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, item_id) DO UPDATE SET read_at = excluded.read_at
            """,
            batch,
        )


def mark_all_read(*, subscription_id: str | None = None) -> None:
    """批量全部已读 —— INSERT ... SELECT 一次完成，无需应用层循环。"""
    _ensure_schema()
    uid = get_user_id()
    now = _now_iso()
    extra_clause = "AND fi.subscription_id = ?" if subscription_id else ""
    params: list[Any] = [uid, now, uid, uid]
    if subscription_id:
        params.append(subscription_id)
    with connect() as conn:
        conn.execute(
            f"""
            INSERT INTO feed_item_reads (user_id, item_id, read_at)
            SELECT ?, fi.id, ?
            FROM feed_items fi
            INNER JOIN feed_subscriptions fs ON fs.id = fi.subscription_id AND fs.user_id = ?
            LEFT JOIN feed_item_reads fir ON fir.item_id = fi.id AND fir.user_id = ?
            WHERE fir.read_at IS NULL {extra_clause}
            ON CONFLICT(user_id, item_id) DO UPDATE SET read_at = excluded.read_at
            """,
            params,
        )


def mark_unread(item_ids: list[str]) -> None:
    if not item_ids:
        return
    _ensure_schema()
    uid = get_user_id()
    placeholders = ",".join("?" for _ in item_ids)
    with connect() as conn:
        conn.execute(
            f"DELETE FROM feed_item_reads WHERE user_id = ? AND item_id IN ({placeholders})",
            (uid, *item_ids),
        )


def purge_old_items(*, retention_days: int = FEED_RETENTION_DAYS) -> int:
    _ensure_schema()
    cutoff = (datetime.now() - timedelta(days=max(1, retention_days))).isoformat(timespec="seconds")
    with connect() as conn:
        old_ids = conn.execute("SELECT id FROM feed_items WHERE published_at < ?", (cutoff,)).fetchall()
        if old_ids:
            placeholders = ",".join("?" for _ in old_ids)
            conn.execute(
                f"DELETE FROM feed_item_reads WHERE item_id IN ({placeholders})",
                tuple(row["id"] for row in old_ids),
            )
        cursor = conn.execute("DELETE FROM feed_items WHERE published_at < ?", (cutoff,))
    return int(cursor.rowcount)


def list_items_published_on(trade_date: str, *, subscription_id: str | None = None) -> list[FeedItem]:
    _ensure_schema()
    uid = get_user_id()
    prefix = trade_date.strip()[:10]
    clauses = ["fi.published_at LIKE ?"]
    params: list[Any] = [uid, uid, f"{prefix}%"]
    if subscription_id:
        clauses.append("fi.subscription_id = ?")
        params.append(subscription_id)
    where = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            f"{_items_base_sql()} WHERE {where} ORDER BY fi.published_at DESC",
            params,
        ).fetchall()
    return [_row_to_item(row) for row in rows]


__all__ = [
    "SOURCE_TYPE_BILIBILI_UP",
    "count_subscriptions",
    "count_unread",
    "delete_subscription",
    "find_subscription_by_source",
    "get_cursor",
    "get_subscription",
    "insert_items_if_new",
    "insert_subscription",
    "list_items",
    "list_items_published_on",
    "list_subscriptions",
    "mark_all_read",
    "mark_read",
    "mark_unread",
    "purge_old_items",
    "update_cursor",
    "update_subscription",
    "upsert_items",
]
