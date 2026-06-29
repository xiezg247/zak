"""auth schema 表（依赖 search_path 解析）。"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from vnpy_common.storage.tables.app import metadata

users = Table(
    "users",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("username", Text, nullable=False, unique=True),
    Column("display_name", Text, nullable=False, server_default=""),
    Column("password_hash", Text, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

user_preferences = Table(
    "user_preferences",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("namespace", Text, nullable=False),
    Column("key", Text, nullable=False),
    Column("value_json", JSONB, nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
