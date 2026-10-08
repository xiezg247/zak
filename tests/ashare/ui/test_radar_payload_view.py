"""雷达 payload 视图模型纯函数测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.loaders import RadarCardData, RadarRow
from vnpy_ashare.ui.quotes.radar.payload_view import (
    failed_card_placeholder,
    format_radar_status_text,
    radar_row_hint_from_payload,
)
from vnpy_ashare.ui.quotes.radar.watchlist_batch import (
    WatchlistBatchResult,
    add_vt_symbols_to_watchlist,
    format_watchlist_batch_notify,
)


def _row(vt: str, *, name: str = "测试", price: float = 10.0) -> RadarRow:
    return RadarRow(
        vt_symbol=vt,
        name=name,
        symbol=vt.split(".")[0],
        price=price,
        change_pct=1.5,
        metric_label="涨幅",
        metric_value="+1.50%",
        sub_label="",
        sub_value="",
    )


def _card(card_id: str, *rows: RadarRow) -> RadarCardData:
    return RadarCardData(
        card_id=card_id,
        title=card_id,
        subtitle="",
        rows=rows,
        empty_message="" if rows else "空",
        updated_at="",
    )


def test_radar_row_hint_from_payload() -> None:
    payload = {"a": _card("a", _row("600000.SSE", name="浦发", price=11.2))}
    hint = radar_row_hint_from_payload(payload, "600000.SSE")
    assert hint == {
        "vt_symbol": "600000.SSE",
        "symbol": "600000",
        "name": "浦发",
        "last_price": 11.2,
        "change_pct": 1.5,
    }
    assert radar_row_hint_from_payload(payload, "missing") is None


def test_failed_card_placeholder() -> None:
    data = failed_card_placeholder("leader_pick", "timeout")
    assert data.card_id == "leader_pick"
    assert "timeout" in data.empty_message
    assert data.rows == ()


def test_format_radar_status_text() -> None:
    assert "加载中" in format_radar_status_text(active_workers=2, payload={})
    assert format_radar_status_text(active_workers=0, payload={}, resonance={}) == "就绪"
    assert "共振 1 只" in format_radar_status_text(
        active_workers=0,
        payload={},
        resonance={"600000.SSE": 2},
    )


class _FakeWatchlist:
    def __init__(self, *, fail_after: int | None = None, reason: str = "duplicate") -> None:
        self._count = 0
        self._fail_after = fail_after
        self._reason = reason

    def add(self, symbol: str, exchange, name: str = "") -> bool:
        self._count += 1
        if self._fail_after is not None and self._count > self._fail_after:
            return False
        return True

    def add_failure_reason(self, symbol: str, exchange):
        return self._reason


def test_add_vt_symbols_to_watchlist_and_notify() -> None:
    service = _FakeWatchlist()
    result = add_vt_symbols_to_watchlist(
        service,
        [("600000.SSE", "浦发"), ("bad", "x"), ("000001.SZSE", "平安")],
    )
    assert result == WatchlistBatchResult(added=2, skipped=1, full_hit=False)
    notify = format_watchlist_batch_notify(result)
    assert notify.message == "已加入 2 只，跳过 1 只"


def test_watchlist_batch_full() -> None:
    service = _FakeWatchlist(fail_after=1, reason="full")
    result = add_vt_symbols_to_watchlist(
        service,
        [("600000.SSE", "浦发"), ("000001.SZSE", "平安")],
    )
    assert result.full_hit
    assert result.added == 1
    notify = format_watchlist_batch_notify(result)
    assert notify.level == "warning"
    assert "已满" in notify.message
