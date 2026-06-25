"""chat schema 表定义（显式 schema 前缀，避免与 search_path 中其它库重名）。"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, Integer, MetaData, Table, Text, UUID

metadata = MetaData(schema="chat")

chat_sessions = Table(
    "sessions",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False, server_default=""),
    Column("scene", Text, nullable=False, server_default=""),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

chat_messages = Table(
    "messages",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("session_id", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

llm_turn_traces = Table(
    "llm_turn_traces",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("turn_id", Text, primary_key=True),
    Column("session_id", Text, nullable=False),
    Column("turn_index", Integer, nullable=False),
    Column("user_text", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("trace_json", Text, nullable=False),
)

llm_tool_calls = Table(
    "llm_tool_calls",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("session_id", Text, nullable=False),
    Column("tool_name", Text, nullable=False),
    Column("arguments_json", Text, nullable=False, server_default="{}"),
    Column("result_preview", Text, nullable=False, server_default=""),
    Column("success", Integer, nullable=False, server_default="1"),
    Column("created_at", Text, nullable=False),
)
