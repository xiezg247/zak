"""nl_mapper collect_warnings 测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.draft.nl_mapper import collect_warnings


def test_collect_warnings_quote_source_unavailable() -> None:
    with patch(
        "vnpy_ashare.screener.draft.nl_mapper.probe_intraday_market_quotes",
        side_effect=MarketQuotesLoadError("无 Redis"),
    ):
        warnings = collect_warnings(source="quote")
    assert len(warnings) == 1
    assert "Redis" in warnings[0]


def test_collect_warnings_quote_source_ok() -> None:
    with patch("vnpy_ashare.screener.draft.nl_mapper.probe_intraday_market_quotes"):
        assert collect_warnings(source="quote") == []
