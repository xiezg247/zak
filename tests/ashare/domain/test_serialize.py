"""序列化约定测试。"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_row import QuoteRow, quote_row_payload, quote_row_to_dict
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, screening_row_to_dict
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_snapshot_to_dict
from vnpy_common.domain.serialize import dump_json, dump_python


def test_dump_python_and_json_roundtrip() -> None:
    row = QuoteRow(symbol="600000", vt_symbol="600000.SSE", last_price=10.5, change_pct=1.2)
    python_payload = dump_python(row)
    json_payload = dump_json(row)
    assert python_payload["last_price"] == 10.5
    assert json_payload["change_pct"] == 1.2


def test_quote_row_payload_excludes_defaults_keeps_extra() -> None:
    row = QuoteRow(symbol="600000", vt_symbol="600000.SSE", last_price=10.0)
    row["industry"] = "银行"
    slim = quote_row_payload(row)
    full = quote_row_to_dict(row)
    assert slim["industry"] == "银行"
    assert slim["last_price"] == 10.0
    assert "volume" not in slim
    assert full["volume"] == 0.0


def test_screener_result_row_to_dict_uses_slim_quote() -> None:
    row = ScreenerResultRow.from_mapping(
        {
            "symbol": "600519",
            "vt_symbol": "600519.SSE",
            "composite_score": 90.0,
            "hit_reason": "龙头",
        },
    )
    payload = row.to_dict()
    assert payload["composite_score"] == 90.0
    assert payload["hit_reason"] == "龙头"
    assert "volume" not in payload
    assert screening_row_to_dict(row) == payload


def test_signal_snapshot_to_dict_uses_json_mode() -> None:
    snapshot = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2026-06-10",
        signal="buy",
        signal_label="买入",
        signal_date="2026-06-10",
        ref_buy_price=10.0,
        ref_sell_price=None,
        strength=80.0,
        reason_summary="金叉",
        reasons=("MA 金叉",),
        warnings=(),
    )
    payload = signal_snapshot_to_dict(snapshot)
    assert payload["signal"] == "buy"
    assert "reasons" not in payload
