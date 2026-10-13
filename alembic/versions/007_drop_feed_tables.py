"""移除信息流相关表。"""

from __future__ import annotations

from alembic import op

revision = "007_drop_feed_tables"
down_revision = "006_dbbardata_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.feed_item_reads")
    op.execute("DROP TABLE IF EXISTS app.feed_cursors")
    op.execute("DROP INDEX IF EXISTS app.idx_feed_items_published")
    op.execute("DROP INDEX IF EXISTS app.idx_feed_items_sub")
    op.execute("DROP TABLE IF EXISTS app.feed_items")
    op.execute("DROP TABLE IF EXISTS app.feed_subscriptions")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.feed_subscriptions (
            id TEXT PRIMARY KEY,
            user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL DEFAULT 'bilibili_up',
            source_id TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            avatar_url TEXT NOT NULL DEFAULT '',
            config_json TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, source_type, source_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.feed_items (
            id TEXT PRIMARY KEY,
            subscription_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            external_id TEXT NOT NULL,
            item_type TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL,
            author_name TEXT NOT NULL DEFAULT '',
            published_at TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            UNIQUE(source_type, external_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_items_published ON app.feed_items(published_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_items_sub ON app.feed_items(subscription_id, published_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.feed_cursors (
            subscription_id TEXT PRIMARY KEY,
            user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
            last_video_ts INTEGER NOT NULL DEFAULT 0,
            last_dynamic_id TEXT NOT NULL DEFAULT '',
            last_ok_at TEXT,
            last_error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.feed_item_reads (
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            item_id TEXT NOT NULL REFERENCES app.feed_items(id) ON DELETE CASCADE,
            read_at TEXT NOT NULL,
            PRIMARY KEY (user_id, item_id)
        )
        """
    )
