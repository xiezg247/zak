"""5 分钟涨速基准价测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.quotes.misc.speed_baseline import (
    SPEED_BASELINE_AT_KEY,
    SPEED_BASELINE_HASH_KEY,
    SPEED_WINDOW_SEC,
    apply_change_speed_5m,
    compute_change_speed_5m,
)


class _FakePipeline:
    def __init__(self, client: _FakeRedis) -> None:
        self._client = client
        self._ops: list[tuple] = []

    def delete(self, key: str) -> None:
        self._ops.append(("delete", key))

    def hset(self, key: str, mapping: dict[str, str] | None = None, **kwargs) -> None:
        self._ops.append(("hset", key, mapping or {}))

    def set(self, key: str, value: str) -> None:
        self._ops.append(("set", key, value))

    def execute(self) -> None:
        for op in self._ops:
            if op[0] == "delete":
                self._client.hashes.pop(op[1], None)
            elif op[0] == "hset":
                self._client.hashes[op[1]] = dict(op[2])
            elif op[0] == "set":
                self._client.data[op[1]] = op[2]
        self._ops.clear()


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def pipeline(self, transaction: bool = False) -> _FakePipeline:
        return _FakePipeline(self)


def _quote(tf_symbol: str, last_price: float) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=tf_symbol,
        name="测试",
        last_price=last_price,
        prev_close=last_price,
        open_price=last_price,
        high_price=last_price,
        low_price=last_price,
        change_amount=0.0,
        change_pct=0.0,
        turnover_rate=0.0,
        volume=0.0,
    )


def test_compute_change_speed_5m() -> None:
    assert compute_change_speed_5m(10.5, 10.0) == 5.0
    assert compute_change_speed_5m(0.0, 10.0) == 0.0


def test_apply_change_speed_5m_initial_baseline() -> None:
    client = _FakeRedis()
    quotes = {"600000.SH": _quote("600000.SH", 10.0)}
    apply_change_speed_5m(client, quotes)
    assert quotes["600000.SH"].change_speed_5m == 0.0
    assert client.hashes[SPEED_BASELINE_HASH_KEY]["600000.SH"] == "10.0"
    assert client.data[SPEED_BASELINE_AT_KEY]


def test_apply_change_speed_5m_within_window(monkeypatch) -> None:
    baseline_at = 1_000_000.0
    monkeypatch.setattr("vnpy_ashare.quotes.misc.speed_baseline.time.time", lambda: baseline_at + 60.0)
    client = _FakeRedis()
    client.hashes[SPEED_BASELINE_HASH_KEY] = {"600000.SH": "10.0"}
    client.data[SPEED_BASELINE_AT_KEY] = str(baseline_at)
    quotes = {"600000.SH": _quote("600000.SH", 10.5)}
    apply_change_speed_5m(client, quotes)
    assert quotes["600000.SH"].change_speed_5m == 5.0


def test_apply_change_speed_5m_rotates_after_window(monkeypatch) -> None:
    client = _FakeRedis()
    client.hashes[SPEED_BASELINE_HASH_KEY] = {"600000.SH": "10.0"}
    client.data[SPEED_BASELINE_AT_KEY] = "0"
    quotes = {"600000.SH": _quote("600000.SH", 11.0)}

    monkeypatch.setattr("vnpy_ashare.quotes.misc.speed_baseline.time.time", lambda: float(SPEED_WINDOW_SEC + 1))
    apply_change_speed_5m(client, quotes)
    assert quotes["600000.SH"].change_speed_5m == 0.0
    assert client.hashes[SPEED_BASELINE_HASH_KEY]["600000.SH"] == "11.0"
