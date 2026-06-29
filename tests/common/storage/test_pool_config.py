"""PostgreSQL 连接池配置测试。"""

from __future__ import annotations

from vnpy_common.storage import pool as pool_module


def test_pool_size_from_env(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_POOL_SIZE", "8")
    monkeypatch.setenv("POSTGRES_MAX_OVERFLOW", "12")
    assert pool_module.pool_size() == 8
    assert pool_module.pool_max_overflow() == 12


def test_pool_size_clamps_invalid(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_POOL_SIZE", "999")
    monkeypatch.setenv("POSTGRES_MAX_OVERFLOW", "bad")
    assert pool_module.pool_size() == 32
    assert pool_module.pool_max_overflow() == 10


def test_reset_engine_allows_recreate(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_POOL_SIZE", "3")
    pool_module.reset_engine()
    assert pool_module.has_engine() is False
