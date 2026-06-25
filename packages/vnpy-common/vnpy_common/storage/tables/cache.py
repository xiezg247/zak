"""cache schema 表定义。"""

from __future__ import annotations

from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, Table, Text

metadata = MetaData(schema="cache")

watchlist_signal_cache = Table(
    "watchlist_signal_cache",
    metadata,
    Column("vt_symbol", Text, nullable=False),
    Column("config_key", Text, nullable=False),
    Column("bar_as_of", Text, nullable=False),
    Column("payload", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    PrimaryKeyConstraint("vt_symbol", "config_key", "bar_as_of"),
)

watchlist_position_cache = Table(
    "watchlist_position_cache",
    metadata,
    Column("vt_symbol", Text, nullable=False),
    Column("config_key", Text, nullable=False),
    Column("bar_as_of", Text, nullable=False),
    Column("position_key", Text, nullable=False),
    Column("payload", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    PrimaryKeyConstraint("vt_symbol", "config_key", "bar_as_of", "position_key"),
)
