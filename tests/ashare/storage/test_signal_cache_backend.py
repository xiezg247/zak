"""信号 cache backend 单测（memory，无 Redis）。"""

from __future__ import annotations

import pytest

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.backends.memory_signal import MemorySignalCacheBackend
from vnpy_ashare.storage.cache.l1_signal_cache import L1SignalCacheWrapper
from vnpy_ashare.storage.cache.watchlist_signal_cache import WatchlistSignalDiskCache


@pytest.fixture(autouse=True)
def _memory_backend(monkeypatch):
    monkeypatch.setenv("ZAK_SIGNAL_CACHE_BACKEND", "memory")
    monkeypatch.setenv("ZAK_SIGNAL_CACHE_L1_SEC", "0")


def _sample_snapshot(vt_symbol: str = "600519.SSE") -> SignalSnapshot:
    return SignalSnapshot(
        vt_symbol=vt_symbol,
        strategy_id="demo",
        as_of="2026-06-25T10:00:00",
        signal="hold",
        signal_label="观望",
        signal_date="2026-06-25",
        ref_buy_price=None,
        ref_sell_price=None,
        strength=None,
        reason_summary="",
        reasons=(),
        warnings=(),
    )


def test_put_get_roundtrip() -> None:
    cache = WatchlistSignalDiskCache(backend=MemorySignalCacheBackend(), l1_ttl_sec=0)
    snap = _sample_snapshot()
    cache.put(snap, config_key="cfg1", bar_as_of="2026-06-25")
    loaded = cache.get("600519.SSE", "cfg1", "2026-06-25")
    assert loaded is not None
    assert loaded.vt_symbol == "600519.SSE"
    assert loaded.signal == "hold"


def test_load_many_uses_exact_bar_as_of() -> None:
    backend = MemorySignalCacheBackend()
    backend.put(_sample_snapshot("600519.SSE"), config_key="cfg1", bar_as_of="2026-06-25")
    cache = WatchlistSignalDiskCache(backend=backend, l1_ttl_sec=0)
    loaded = cache.load_many(
        ["600519.SSE", "000001.SZ"],
        config_key="cfg1",
        bar_as_of_for=lambda _vt: "2026-06-25",
    )
    assert set(loaded.keys()) == {"600519.SSE"}


def test_l1_skips_second_backend_load_many(monkeypatch) -> None:
    backend = MemorySignalCacheBackend()
    backend.put(_sample_snapshot(), config_key="cfg1", bar_as_of="2026-06-25")

    calls = {"count": 0}
    real_load_many = backend.load_many

    def counting_load_many(*args, **kwargs):
        calls["count"] += 1
        return real_load_many(*args, **kwargs)

    monkeypatch.setattr(backend, "load_many", counting_load_many)
    wrapped = L1SignalCacheWrapper(backend, ttl_sec=5.0)
    kwargs = {
        "config_key": "cfg1",
        "bar_as_of_for": lambda _vt: "2026-06-25",
    }
    first = wrapped.load_many(["600519.SSE"], **kwargs)
    second = wrapped.load_many(["600519.SSE"], **kwargs)
    assert first == second
    assert calls["count"] == 1
