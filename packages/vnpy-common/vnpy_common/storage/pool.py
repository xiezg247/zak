"""PostgreSQL 连接池 —— SQLAlchemy Engine 单例。

设计：
- 全局单例 Engine，自带 QueuePool 管理连接复用/回收/健康检查
- 只暴露 get_connection，不引入 ORM Session
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.engine import Connection


_ENGINE_LOCK = threading.Lock()

_POOL_SIZE = 5
_POOL_MAX_OVERFLOW = 10
_POOL_RECYCLE_SEC = 3600
_CONNECT_TIMEOUT = 10

_engine: Engine | None = None


def _create_engine(url: str) -> Engine:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import QueuePool

    return create_engine(
        url,
        poolclass=QueuePool,
        pool_size=_POOL_SIZE,
        max_overflow=_POOL_MAX_OVERFLOW,
        pool_recycle=_POOL_RECYCLE_SEC,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": _CONNECT_TIMEOUT,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    )


def get_engine(url: str) -> Engine:
    """获取或创建 Engine 单例（同一 url 复用）。"""
    global _engine
    if _engine is None:
        with _ENGINE_LOCK:
            if _engine is None:
                _engine = _create_engine(url)
    return _engine


def get_connection(url: str) -> Connection:
    """从池获取一条连接。"""
    return get_engine(url).connect()


def reset_engine() -> None:
    """测试 teardown：释放所有连接。"""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def has_engine() -> bool:
    return _engine is not None
