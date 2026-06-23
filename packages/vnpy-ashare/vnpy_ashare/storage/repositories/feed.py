"""信息流 SQLite repository。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.domain.feed.models import (
    FEED_RETENTION_DAYS,
    FeedItem,
    FeedItemDraft,
    FeedSubscription,
    FeedSubscriptionConfig,
    SOURCE_TYPE_BILIBILI_UP,
)
from vnpy_ashare.storage.connection import connect, init_app_db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feed_subscriptions (
    id              TEXT PRIMARY KEY,
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
    last_video_ts   INTEGER NOT NULL DEFAULT 0,
    last_dynamic_id TEXT NOT NULL DEFAULT '',
    last_ok_at      TEXT,
    last_error      TEXT NOT NULL DEFAULT ''
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
        read_at=row["read_at"],
        created_at=row["created_at"],
    )


def count_subscriptions() -> int:
    _ensure_schema()
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM feed_subscriptions").fetchone()
    return int(row["c"] if row else 0)


def list_subscriptions(*, enabled_only: bool = False) -> list[FeedSubscription]:
    _ensure_schema()
    sql = "SELECT * FROM feed_subscriptions"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY sort_order ASC, created_at ASC"
    with connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_row_to_subscription(row) for row in rows]


def get_subscription(subscription_id: str) -> FeedSubscription | None:
    _ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM feed_subscriptions WHERE id = ?",
            (subscription_id,),
        ).fetchone()
    return _row_to_subscription(row) if row is not None else None


def find_subscription_by_source(source_type: str, source_id: str) -> FeedSubscription | None:
    _ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM feed_subscriptions WHERE source_type = ? AND source_id = ?",
            (source_type, source_id),
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
    now = _now_iso()
    sub_id = str(uuid.uuid4())
    cfg = config or FeedSubscriptionConfig()
    with connect() as conn:
        row = conn.execute("SELECT COALESCE(MAX(sort_order), -1) AS m FROM feed_subscriptions").fetchone()
        sort_order = int(row["m"] if row else -1) + 1
        conn.execute(
            "INSERT INTO feed_subscriptions("
            "id, source_type, source_id, display_name, avatar_url, config_json, enabled, sort_order, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (
                sub_id,
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
            "INSERT OR IGNORE INTO feed_cursors(subscription_id, last_video_ts, last_dynamic_id, last_error) VALUES (?, 0, '', '')",
            (sub_id,),
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
    values.append(subscription_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE feed_subscriptions SET {', '.join(fields)} WHERE id = ?",
            values,
        )


def delete_subscription(subscription_id: str) -> None:
    _ensure_schema()
    with connect() as conn:
        conn.execute("DELETE FROM feed_cursors WHERE subscription_id = ?", (subscription_id,))
        conn.execute("DELETE FROM feed_subscriptions WHERE id = ?", (subscription_id,))


def get_cursor(subscription_id: str) -> dict[str, Any]:
    _ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT last_video_ts, last_dynamic_id, last_ok_at, last_error FROM feed_cursors WHERE subscription_id = ?",
            (subscription_id,),
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
    cursor = get_cursor(subscription_id)
    with connect() as conn:
        conn.execute(
            "INSERT INTO feed_cursors(subscription_id, last_video_ts, last_dynamic_id, last_ok_at, last_error) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(subscription_id) DO UPDATE SET "
            "last_video_ts = excluded.last_video_ts, "
            "last_dynamic_id = excluded.last_dynamic_id, "
            "last_ok_at = excluded.last_ok_at, "
            "last_error = excluded.last_error",
            (
                subscription_id,
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
    if not drafts:
        return []
    _ensure_schema()
    now = _now_iso()
    inserted: list[FeedItem] = []
    with connect() as conn:
        for draft in drafts:
            item_id = str(uuid.uuid4())
            cursor = conn.execute(
                "INSERT OR IGNORE INTO feed_items("
                "id, subscription_id, source_type, external_id, item_type, title, summary, url, "
                "author_name, published_at, payload_json, read_at, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                (
                    item_id,
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
                ),
            )
            if cursor.rowcount <= 0:
                continue
            row = conn.execute("SELECT * FROM feed_items WHERE id = ?", (item_id,)).fetchone()
            if row is not None:
                inserted.append(_row_to_item(row))
    return inserted


def list_items(
    *,
    limit: int = 50,
    unread_only: bool = False,
    subscription_id: str | None = None,
) -> list[FeedItem]:
    _ensure_schema()
    limit = max(1, min(int(limit), 200))
    clauses: list[str] = []
    params: list[Any] = []
    if unread_only:
        clauses.append("read_at IS NULL")
    if subscription_id:
        clauses.append("subscription_id = ?")
        params.append(subscription_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM feed_items {where} ORDER BY published_at DESC, created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [_row_to_item(row) for row in rows]


def count_unread(*, subscription_id: str | None = None) -> int:
    _ensure_schema()
    if subscription_id:
        sql = "SELECT COUNT(*) AS c FROM feed_items WHERE read_at IS NULL AND subscription_id = ?"
        params: tuple[Any, ...] = (subscription_id,)
    else:
        sql = "SELECT COUNT(*) AS c FROM feed_items WHERE read_at IS NULL"
        params = ()
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return int(row["c"] if row else 0)


def mark_read(item_ids: list[str]) -> None:
    if not item_ids:
        return
    _ensure_schema()
    now = _now_iso()
    placeholders = ",".join("?" for _ in item_ids)
    with connect() as conn:
        conn.execute(
            f"UPDATE feed_items SET read_at = ? WHERE id IN ({placeholders}) AND read_at IS NULL",
            (now, *item_ids),
        )


def mark_all_read(*, subscription_id: str | None = None) -> None:
    _ensure_schema()
    now = _now_iso()
    with connect() as conn:
        if subscription_id:
            conn.execute(
                "UPDATE feed_items SET read_at = ? WHERE subscription_id = ? AND read_at IS NULL",
                (now, subscription_id),
            )
        else:
            conn.execute("UPDATE feed_items SET read_at = ? WHERE read_at IS NULL", (now,))


def mark_unread(item_ids: list[str]) -> None:
    if not item_ids:
        return
    _ensure_schema()
    placeholders = ",".join("?" for _ in item_ids)
    with connect() as conn:
        conn.execute(
            f"UPDATE feed_items SET read_at = NULL WHERE id IN ({placeholders})",
            item_ids,
        )


def purge_old_items(*, retention_days: int = FEED_RETENTION_DAYS) -> int:
    _ensure_schema()
    cutoff = (datetime.now() - timedelta(days=max(1, retention_days))).isoformat(timespec="seconds")
    with connect() as conn:
        cursor = conn.execute("DELETE FROM feed_items WHERE published_at < ?", (cutoff,))
    return int(cursor.rowcount)


def list_items_published_on(trade_date: str, *, subscription_id: str | None = None) -> list[FeedItem]:
    _ensure_schema()
    prefix = trade_date.strip()[:10]
    clauses = ["published_at LIKE ?"]
    params: list[Any] = [f"{prefix}%"]
    if subscription_id:
        clauses.append("subscription_id = ?")
        params.append(subscription_id)
    where = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM feed_items WHERE {where} ORDER BY published_at DESC",
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
]
