"""选股结果监管异动 enrichment 测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.enrich.regulatory import enrich_regulatory_tags


def _row(symbol: str = "600000") -> ScreenerResultRow:
    return ScreenerResultRow.from_mapping(
        {
            "vt_symbol": f"{symbol}.SSE",
            "symbol": symbol,
            "name": symbol,
            "source": "radar_leader",
        }
    )


@patch("vnpy_ashare.screener.enrich.regulatory.assess_regulatory_deviation")
@patch("vnpy_ashare.screener.enrich.regulatory.load_daily_bars_batch")
def test_enrich_regulatory_tags_writes_hint(mock_bars, mock_assess):
    mock_bars.return_value = {("600000", Exchange.SSE): [object()] * 20}
    snapshot = MagicMock(risk_level="watch", summary="10日3次涨停")
    mock_assess.return_value = snapshot

    rows = enrich_regulatory_tags([_row()])
    assert rows[0].tags.get("regulatory_hint") == "10日3次涨停"
    assert rows[0].tags.get("regulatory_risk") == "watch"


@patch("vnpy_ashare.screener.enrich.regulatory.load_daily_bars_batch", return_value={})
def test_enrich_regulatory_tags_skips_short_history(_bars):
    rows = enrich_regulatory_tags([_row()])
    assert "regulatory_hint" not in rows[0].tags
