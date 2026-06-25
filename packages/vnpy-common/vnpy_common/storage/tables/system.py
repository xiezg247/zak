"""system schema 表（依赖 search_path 解析）。"""

from __future__ import annotations

from sqlalchemy import Column, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from vnpy_common.storage.tables.app import metadata

scheduler_config = Table(
    "scheduler_config",
    metadata,
    Column("id", Text, primary_key=True, server_default="default"),
    Column("config_json", JSONB, nullable=False, server_default="{}"),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
)
