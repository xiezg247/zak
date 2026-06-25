"""Chat 库 trace / tool_calls 连接（兼容旧 import）。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from vnpy_llm.chat.store import _connect


@contextmanager
def trace_connect() -> Iterator[Any]:
    with _connect() as conn:
        yield conn


@contextmanager
def tool_calls_connect() -> Iterator[Any]:
    with _connect() as conn:
        yield conn
