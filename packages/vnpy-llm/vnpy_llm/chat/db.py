"""Chat 库 trace / tool_calls（PostgreSQL chat schema）。"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any

import vnpy_llm.chat.store as chat_store


@contextmanager
def trace_connect() -> Iterator[Any]:
    with chat_store._connect() as conn:
        yield conn


@contextmanager
def tool_calls_connect() -> Iterator[Any]:
    with chat_store._connect() as conn:
        yield conn
