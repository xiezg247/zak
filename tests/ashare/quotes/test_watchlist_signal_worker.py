"""自选信号 Worker payload 测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.ui.quotes.watchlist_signals.worker import (
    WatchlistSignalWorkerPayload,
    unwrap_worker_payload,
)


def test_unwrap_worker_payload_accepts_dataclass() -> None:
    payload = WatchlistSignalWorkerPayload(signals={"600000.SH": object()}, continuations={})
    assert unwrap_worker_payload(payload) is payload


def test_unwrap_worker_payload_accepts_signals_dict() -> None:
    raw = {"600000.SH": object()}
    payload = unwrap_worker_payload(raw)
    assert payload.signals == raw
    assert payload.continuations == {}


def test_unwrap_worker_payload_accepts_nested_dict() -> None:
    raw = {"signals": {"600000.SH": object()}, "continuations": {"600000.SH": object()}}
    payload = unwrap_worker_payload(raw)
    assert payload.signals == raw["signals"]
    assert payload.continuations == raw["continuations"]


def test_unwrap_worker_payload_rejects_other_types() -> None:
    with pytest.raises(TypeError, match="WatchlistSignalWorkerPayload"):
        unwrap_worker_payload(["bad"])
