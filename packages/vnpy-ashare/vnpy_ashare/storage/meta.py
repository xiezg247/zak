"""系统 meta KV（PostgreSQL system.meta）。"""

from __future__ import annotations

from vnpy_ashare.storage.repository import MetaRepository

_meta = MetaRepository()


def get_meta(key: str) -> str | None:
    return _meta.get_value(key)


def set_meta(key: str, value: str) -> None:
    _meta.upsert_value(key, value)


def delete_meta(key: str) -> None:
    _meta.delete_keys(key)
