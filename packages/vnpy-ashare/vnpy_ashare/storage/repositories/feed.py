"""信息流 repository（PostgreSQL app schema）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.domain.feed.models import (
    FEED_RETENTION_DAYS,
    SOURCE_TYPE_BILIBILI_UP,
    FeedItem,
    FeedItemDraft,
    FeedSubscription,
    FeedSubscriptionConfig,
)
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.storage.repository.upsert import insert_ignore
from vnpy_common.storage.tables import feed_cursors as fc
from vnpy_common.storage.tables import feed_item_reads as fir
from vnpy_common.storage.tables import feed_items as fi
from vnpy_common.storage.tables import feed_subscriptions as fs


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


class FeedRepository(AppUserScopedRepository):
    table = fs

    def _items_select(self):
        uid = self.current_user_id()
        return (
            select(fi, fir.c.read_at.label("user_read_at"))
            .select_from(fi)
            .join(fs, (fs.c.id == fi.c.subscription_id) & (fs.c.user_id == uid))
            .outerjoin(fir, (fir.c.item_id == fi.c.id) & (fir.c.user_id == uid))
        )

    def count_subscriptions(self) -> int:
        return self.count_for_user()

    def list_subscriptions(self, *, enabled_only: bool = False) -> list[FeedSubscription]:
        extras = (fs.c.enabled == 1,) if enabled_only else ()
        rows = self.list_for_user(
            *fs.c,
            extras=extras or None,
            order_by=(fs.c.sort_order.asc(), fs.c.created_at.asc()),
        )
        return [_row_to_subscription(row) for row in rows]

    def get_subscription(self, subscription_id: str) -> FeedSubscription | None:
        rows = self.list_for_user(*fs.c, extras=(fs.c.id == subscription_id,), limit=1)
        return _row_to_subscription(rows[0]) if rows else None

    def find_subscription_by_source(self, source_type: str, source_id: str) -> FeedSubscription | None:
        rows = self.list_for_user(
            *fs.c,
            extras=(fs.c.source_type == source_type, fs.c.source_id == source_id),
            limit=1,
        )
        return _row_to_subscription(rows[0]) if rows else None

    def insert_subscription(
        self,
        *,
        source_type: str,
        source_id: str,
        display_name: str,
        avatar_url: str = "",
        config: FeedSubscriptionConfig | None = None,
    ) -> FeedSubscription:
        now = _now_iso()
        sub_id = str(uuid.uuid4())
        cfg = config or FeedSubscriptionConfig()

        def _write(conn) -> None:
            row = conn.execute_stmt(
                select(func.coalesce(func.max(fs.c.sort_order), -1).label("m")).where(self.scope())
            ).fetchone()
            sort_order = int(row["m"] if row else -1) + 1
            self.insert_for_user(
                conn,
                id=sub_id,
                source_type=source_type,
                source_id=source_id,
                display_name=display_name,
                avatar_url=avatar_url,
                config_json=json.dumps(cfg.model_dump(), ensure_ascii=False),
                enabled=1,
                sort_order=sort_order,
                created_at=now,
                updated_at=now,
            )
            insert_ignore(
                conn,
                fc,
                {
                    "subscription_id": sub_id,
                    "user_id": self.current_user_id(),
                    "last_video_ts": 0,
                    "last_dynamic_id": "",
                    "last_error": "",
                },
            )

        self.run(_write)
        sub = self.get_subscription(sub_id)
        assert sub is not None
        return sub

    def update_subscription(
        self,
        subscription_id: str,
        *,
        display_name: str | None = None,
        avatar_url: str | None = None,
        config: FeedSubscriptionConfig | None = None,
        enabled: bool | None = None,
    ) -> None:
        values: dict[str, Any] = {}
        if display_name is not None:
            values["display_name"] = display_name
        if avatar_url is not None:
            values["avatar_url"] = avatar_url
        if config is not None:
            values["config_json"] = json.dumps(config.model_dump(), ensure_ascii=False)
        if enabled is not None:
            values["enabled"] = 1 if enabled else 0
        if not values:
            return
        values["updated_at"] = _now_iso()
        self.update_matching(values, self.scope(fs.c.id == subscription_id))

    def delete_subscription(self, subscription_id: str) -> None:
        def _write(conn) -> None:
            conn.execute_stmt(
                delete(fc).where(self.scope_table(fc, fc.c.subscription_id == subscription_id))
            )
            self.delete_where(conn, self.scope(fs.c.id == subscription_id))

        self.run(_write)

    def get_cursor(self, subscription_id: str) -> dict[str, Any]:
        row = self.fetchone(
            select(
                fc.c.last_video_ts,
                fc.c.last_dynamic_id,
                fc.c.last_ok_at,
                fc.c.last_error,
            ).where(self.scope_table(fc, fc.c.subscription_id == subscription_id))
        )
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
        self,
        subscription_id: str,
        *,
        last_video_ts: int | None = None,
        last_dynamic_id: str | None = None,
        last_ok_at: str | None = None,
        last_error: str | None = None,
    ) -> None:
        cursor = self.get_cursor(subscription_id)
        values = {
            "subscription_id": subscription_id,
            "user_id": self.current_user_id(),
            "last_video_ts": int(last_video_ts if last_video_ts is not None else cursor["last_video_ts"]),
            "last_dynamic_id": str(last_dynamic_id if last_dynamic_id is not None else cursor["last_dynamic_id"]),
            "last_ok_at": last_ok_at if last_ok_at is not None else cursor["last_ok_at"],
            "last_error": last_error if last_error is not None else cursor["last_error"],
        }

        def _write(conn) -> None:
            stmt = pg_insert(fc).values(values)
            excluded = stmt.excluded
            stmt = stmt.on_conflict_do_update(
                index_elements=[fc.c.subscription_id],
                set_={
                    "last_video_ts": excluded.last_video_ts,
                    "last_dynamic_id": excluded.last_dynamic_id,
                    "last_ok_at": excluded.last_ok_at,
                    "last_error": excluded.last_error,
                },
            )
            conn.execute_stmt(stmt)

        self.run(_write)

    def insert_items_if_new(
        self,
        subscription_id: str,
        source_type: str,
        drafts: list[FeedItemDraft],
    ) -> list[FeedItem]:
        """批量插入新条目（ON CONFLICT DO NOTHING），一次性返回新插入的条目。"""
        if not drafts:
            return []
        now = _now_iso()
        item_ids = [str(uuid.uuid4()) for _ in drafts]
        values = [
            {
                "id": item_ids[i],
                "subscription_id": subscription_id,
                "source_type": source_type,
                "external_id": draft.external_id,
                "item_type": draft.item_type,
                "title": draft.title,
                "summary": draft.summary,
                "url": draft.url,
                "author_name": draft.author_name,
                "published_at": draft.published_at,
                "payload_json": json.dumps(draft.payload, ensure_ascii=False),
                "read_at": None,
                "created_at": now,
            }
            for i, draft in enumerate(drafts)
        ]
        ext_ids = [d.external_id for d in drafts]

        def _write(conn) -> list[FeedItem]:
            conn.execute_stmt(
                pg_insert(fi)
                .values(values)
                .on_conflict_do_nothing(index_elements=[fi.c.source_type, fi.c.external_id])
            )
            rows = conn.execute_stmt(
                select(fi).where(
                    fi.c.source_type == source_type,
                    fi.c.external_id.in_(ext_ids),
                    fi.c.created_at == now,
                )
            ).fetchall()
            return [_row_to_item(row) for row in rows]

        return self.run(_write)

    def upsert_items(
        self,
        subscription_id: str,
        source_type: str,
        drafts: list[FeedItemDraft],
    ) -> list[FeedItem]:
        """批量插入或更新条目（保留用户已读状态）；返回本次新插入的条目。"""
        if not drafts:
            return []
        now = _now_iso()
        ext_ids = [d.external_id for d in drafts]

        def _write(conn) -> list[FeedItem]:
            existing_rows = conn.execute_stmt(
                select(fi.c.id, fi.c.external_id).where(
                    fi.c.source_type == source_type,
                    fi.c.external_id.in_(ext_ids),
                )
            ).fetchall()
            existing_map: dict[str, str] = {str(r["external_id"]): str(r["id"]) for r in existing_rows}

            for draft in drafts:
                item_id = existing_map.get(draft.external_id)
                if item_id is None:
                    continue
                conn.execute_stmt(
                    update(fi)
                    .where(fi.c.id == item_id)
                    .values(
                        item_type=draft.item_type,
                        title=draft.title,
                        summary=draft.summary,
                        url=draft.url,
                        author_name=draft.author_name,
                        published_at=draft.published_at,
                        payload_json=json.dumps(draft.payload, ensure_ascii=False),
                    )
                )

            new_drafts = [d for d in drafts if d.external_id not in existing_map]
            if not new_drafts:
                return []

            item_ids = [str(uuid.uuid4()) for _ in new_drafts]
            insert_values = [
                {
                    "id": item_ids[i],
                    "subscription_id": subscription_id,
                    "source_type": source_type,
                    "external_id": draft.external_id,
                    "item_type": draft.item_type,
                    "title": draft.title,
                    "summary": draft.summary,
                    "url": draft.url,
                    "author_name": draft.author_name,
                    "published_at": draft.published_at,
                    "payload_json": json.dumps(draft.payload, ensure_ascii=False),
                    "read_at": None,
                    "created_at": now,
                }
                for i, draft in enumerate(new_drafts)
            ]
            conn.execute_stmt(insert(fi).values(insert_values))

            new_ext_ids = [d.external_id for d in new_drafts]
            rows = conn.execute_stmt(
                select(fi).where(
                    fi.c.source_type == source_type,
                    fi.c.external_id.in_(new_ext_ids),
                    fi.c.created_at == now,
                )
            ).fetchall()
            return [_row_to_item(row) for row in rows]

        return self.run(_write)

    def list_items(
        self,
        *,
        limit: int = 50,
        unread_only: bool = False,
        subscription_id: str | None = None,
    ) -> list[FeedItem]:
        limit = max(1, min(int(limit), 200))
        clauses: list[Any] = []
        if unread_only:
            clauses.append(fir.c.read_at.is_(None))
        if subscription_id:
            clauses.append(fi.c.subscription_id == subscription_id)
        stmt = self._items_select()
        if clauses:
            stmt = stmt.where(*clauses)
        stmt = stmt.order_by(fi.c.published_at.desc(), fi.c.created_at.desc()).limit(limit)
        rows = self.fetchall(stmt)
        return [_row_to_item(row) for row in rows]

    def count_unread(self, *, subscription_id: str | None = None) -> int:
        uid = self.current_user_id()
        clauses = [fir.c.read_at.is_(None)]
        if subscription_id:
            clauses.append(fi.c.subscription_id == subscription_id)
        stmt = (
            select(func.count())
            .select_from(fi)
            .join(fs, (fs.c.id == fi.c.subscription_id) & (fs.c.user_id == uid))
            .outerjoin(fir, (fir.c.item_id == fi.c.id) & (fir.c.user_id == uid))
            .where(*clauses)
        )
        row = self.fetchone(stmt)
        return int(row[0]) if row is not None else 0

    def mark_read(self, item_ids: list[str]) -> None:
        if not item_ids:
            return
        uid = self.current_user_id()
        now = _now_iso()
        values = [{"user_id": uid, "item_id": item_id, "read_at": now} for item_id in item_ids]

        def _write(conn) -> None:
            stmt = pg_insert(fir).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[fir.c.user_id, fir.c.item_id],
                    set_={"read_at": excluded.read_at},
                )
            )

        self.run(_write)

    def mark_all_read(self, *, subscription_id: str | None = None) -> None:
        uid = self.current_user_id()
        now = _now_iso()
        unread = (
            select(literal(uid), fi.c.id, literal(now))
            .select_from(fi)
            .join(fs, (fs.c.id == fi.c.subscription_id) & (fs.c.user_id == uid))
            .outerjoin(fir, (fir.c.item_id == fi.c.id) & (fir.c.user_id == uid))
            .where(fir.c.read_at.is_(None))
        )
        if subscription_id:
            unread = unread.where(fi.c.subscription_id == subscription_id)

        def _write(conn) -> None:
            stmt = pg_insert(fir).from_select([fir.c.user_id, fir.c.item_id, fir.c.read_at], unread)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[fir.c.user_id, fir.c.item_id],
                    set_={"read_at": excluded.read_at},
                )
            )

        self.run(_write)

    def mark_unread(self, item_ids: list[str]) -> None:
        if not item_ids:
            return
        uid = self.current_user_id()

        def _write(conn) -> None:
            conn.execute_stmt(delete(fir).where(fir.c.user_id == uid, fir.c.item_id.in_(item_ids)))

        self.run(_write)

    def purge_old_items(self, *, retention_days: int = FEED_RETENTION_DAYS) -> int:
        cutoff = (datetime.now() - timedelta(days=max(1, retention_days))).isoformat(timespec="seconds")

        def _write(conn) -> int:
            old_rows = conn.execute_stmt(select(fi.c.id).where(fi.c.published_at < cutoff)).fetchall()
            if old_rows:
                old_ids = [row["id"] for row in old_rows]
                conn.execute_stmt(delete(fir).where(fir.c.item_id.in_(old_ids)))
            cursor = conn.execute_stmt(delete(fi).where(fi.c.published_at < cutoff))
            return int(cursor.rowcount)

        return self.run(_write)

    def list_items_published_on(self, trade_date: str, *, subscription_id: str | None = None) -> list[FeedItem]:
        prefix = trade_date.strip()[:10]
        clauses = [fi.c.published_at.like(f"{prefix}%")]
        if subscription_id:
            clauses.append(fi.c.subscription_id == subscription_id)
        stmt = self._items_select().where(*clauses).order_by(fi.c.published_at.desc())
        rows = self.fetchall(stmt)
        return [_row_to_item(row) for row in rows]


_repo = FeedRepository()


def _ensure_schema() -> None:
    """兼容旧测试：仅 init app DB（表由 Alembic 管理）。"""
    _repo.prepare()


def count_subscriptions() -> int:
    return _repo.count_subscriptions()


def list_subscriptions(*, enabled_only: bool = False) -> list[FeedSubscription]:
    return _repo.list_subscriptions(enabled_only=enabled_only)


def get_subscription(subscription_id: str) -> FeedSubscription | None:
    return _repo.get_subscription(subscription_id)


def find_subscription_by_source(source_type: str, source_id: str) -> FeedSubscription | None:
    return _repo.find_subscription_by_source(source_type, source_id)


def insert_subscription(
    *,
    source_type: str,
    source_id: str,
    display_name: str,
    avatar_url: str = "",
    config: FeedSubscriptionConfig | None = None,
) -> FeedSubscription:
    return _repo.insert_subscription(
        source_type=source_type,
        source_id=source_id,
        display_name=display_name,
        avatar_url=avatar_url,
        config=config,
    )


def update_subscription(
    subscription_id: str,
    *,
    display_name: str | None = None,
    avatar_url: str | None = None,
    config: FeedSubscriptionConfig | None = None,
    enabled: bool | None = None,
) -> None:
    _repo.update_subscription(
        subscription_id,
        display_name=display_name,
        avatar_url=avatar_url,
        config=config,
        enabled=enabled,
    )


def delete_subscription(subscription_id: str) -> None:
    _repo.delete_subscription(subscription_id)


def get_cursor(subscription_id: str) -> dict[str, Any]:
    return _repo.get_cursor(subscription_id)


def update_cursor(
    subscription_id: str,
    *,
    last_video_ts: int | None = None,
    last_dynamic_id: str | None = None,
    last_ok_at: str | None = None,
    last_error: str | None = None,
) -> None:
    _repo.update_cursor(
        subscription_id,
        last_video_ts=last_video_ts,
        last_dynamic_id=last_dynamic_id,
        last_ok_at=last_ok_at,
        last_error=last_error,
    )


def insert_items_if_new(
    subscription_id: str,
    source_type: str,
    drafts: list[FeedItemDraft],
) -> list[FeedItem]:
    return _repo.insert_items_if_new(subscription_id, source_type, drafts)


def upsert_items(
    subscription_id: str,
    source_type: str,
    drafts: list[FeedItemDraft],
) -> list[FeedItem]:
    return _repo.upsert_items(subscription_id, source_type, drafts)


def list_items(
    *,
    limit: int = 50,
    unread_only: bool = False,
    subscription_id: str | None = None,
) -> list[FeedItem]:
    return _repo.list_items(limit=limit, unread_only=unread_only, subscription_id=subscription_id)


def count_unread(*, subscription_id: str | None = None) -> int:
    return _repo.count_unread(subscription_id=subscription_id)


def mark_read(item_ids: list[str]) -> None:
    _repo.mark_read(item_ids)


def mark_all_read(*, subscription_id: str | None = None) -> None:
    _repo.mark_all_read(subscription_id=subscription_id)


def mark_unread(item_ids: list[str]) -> None:
    _repo.mark_unread(item_ids)


def purge_old_items(*, retention_days: int = FEED_RETENTION_DAYS) -> int:
    return _repo.purge_old_items(retention_days=retention_days)


def list_items_published_on(trade_date: str, *, subscription_id: str | None = None) -> list[FeedItem]:
    return _repo.list_items_published_on(trade_date, subscription_id=subscription_id)


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
