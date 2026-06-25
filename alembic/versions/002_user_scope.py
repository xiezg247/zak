"""用户私有表增加 user_id 与 feed_item_reads。"""

from __future__ import annotations

from alembic import op

revision = "002_user_scope"
down_revision = "001_initial"
branch_labels = None
depends_on = None

APP_TABLES = (
    "watchlist",
    "watchlist_groups",
    "watchlist_group_members",
    "watchlist_positions",
    "stock_note_memos",
    "stock_note_entries",
    "stock_analysis_reports",
    "trading_plans",
    "trading_plan_symbols",
    "trading_playbook_discipline_daily",
    "screener_schemes",
    "screener_recipes",
    "screener_runs",
    "backtest_runs",
    "feed_subscriptions",
    "feed_cursors",
    "notify_delivery_log",
)

CHAT_TABLES = (
    "sessions",
    "messages",
    "llm_turn_traces",
    "llm_tool_calls",
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            default_uid UUID;
        BEGIN
            SELECT id INTO default_uid FROM auth.users WHERE username = 'default' LIMIT 1;
            IF default_uid IS NULL THEN
                INSERT INTO auth.users (username, display_name, password_hash)
                VALUES (
                    'default',
                    '默认用户',
                    'pbkdf2_sha256$00000000000000000000000000000000$0000000000000000000000000000000000000000000000000000000000000000'
                )
                RETURNING id INTO default_uid;
            END IF;
        END $$;
        """
    )
    default_uid_expr = "(SELECT id FROM auth.users WHERE username = 'default' LIMIT 1)"

    for table in APP_TABLES:
        op.execute(f"ALTER TABLE app.{table} ADD COLUMN IF NOT EXISTS user_id UUID")
        op.execute(f"UPDATE app.{table} SET user_id = {default_uid_expr} WHERE user_id IS NULL")
        op.execute(f"ALTER TABLE app.{table} ALTER COLUMN user_id SET NOT NULL")

    for table in CHAT_TABLES:
        op.execute(f"ALTER TABLE chat.{table} ADD COLUMN IF NOT EXISTS user_id UUID")
        op.execute(f"UPDATE chat.{table} SET user_id = {default_uid_expr} WHERE user_id IS NULL")
        op.execute(f"ALTER TABLE chat.{table} ALTER COLUMN user_id SET NOT NULL")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS app.feed_item_reads (
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            item_id TEXT NOT NULL REFERENCES app.feed_items(id) ON DELETE CASCADE,
            read_at TEXT NOT NULL,
            PRIMARY KEY (user_id, item_id)
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO app.feed_item_reads (user_id, item_id, read_at)
        SELECT {default_uid_expr}, id, read_at
        FROM app.feed_items
        WHERE read_at IS NOT NULL AND read_at != ''
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.feed_item_reads")
    for table in reversed(CHAT_TABLES):
        op.execute(f"ALTER TABLE chat.{table} DROP COLUMN IF EXISTS user_id")
    for table in reversed(APP_TABLES):
        op.execute(f"ALTER TABLE app.{table} DROP COLUMN IF EXISTS user_id")
