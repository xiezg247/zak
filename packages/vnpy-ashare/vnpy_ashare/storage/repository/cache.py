"""cache schema Repository 基类。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from vnpy_common.storage.compat import DbConnection
from vnpy_common.storage.repository import BaseRepository
from vnpy_common.storage.session import cache_session


class CacheBaseRepository(BaseRepository):
    """绑定 cache schema 会话（search_path 含 cache）。"""

    @contextmanager
    def session(self) -> Iterator[DbConnection]:
        self.prepare()
        with cache_session("", "") as conn:
            yield conn
