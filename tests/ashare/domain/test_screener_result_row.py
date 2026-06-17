"""ScreenerResultRow 与 QuoteSnapshot 领域测试。"""

from __future__ import annotations

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow


def test_screener_result_row_split_and_merge() -> None:
    raw = {
        "symbol": "600519",
        "vt_symbol": "600519.SSE",
        "name": "贵州茅台",
        "change_pct": 2.5,
        "composite_score": 88.0,
        "hit_reason": "动量+资金",
        "flow_kind": "main",
    }
    row = ScreenerResultRow.from_mapping(raw)
    assert row.quote.vt_symbol == "600519.SSE"
    assert row.scores["composite_score"] == 88.0
    assert row.tags["hit_reason"] == "动量+资金"
    merged = row.to_dict()
    assert merged["composite_score"] == 88.0
    assert merged["hit_reason"] == "动量+资金"
    assert row.get("change_pct") == 2.5
