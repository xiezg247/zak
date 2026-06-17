"""投研团队市场环境预取测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.market.market_overview_loaders import SectorRankItem
from vnpy_ashare.services.analysis_detail.market_context import build_team_market_context


def _sample_item() -> StockItem:
    return StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")


@patch("vnpy_ashare.services.analysis_detail.market_context.fetch_market_sentiment")
@patch("vnpy_ashare.services.analysis_detail.market_context.get_market_quotes_cache", return_value=[])
@patch("vnpy_ashare.services.analysis_detail.market_context.get_market_overview_context", return_value=None)
@patch("vnpy_ashare.services.analysis_detail.market_context.resolve_benchmark_return_pct", return_value=5.0)
@patch("vnpy_ashare.services.analysis_detail.market_context.compute_relative_index_excess", return_value=3.5)
def test_build_team_market_context_summary(
    _mock_excess: MagicMock,
    _mock_bench: MagicMock,
    _mock_overview: MagicMock,
    _mock_quotes: MagicMock,
    mock_sentiment: MagicMock,
):
    mock_sentiment.return_value = {
        "fear_greed_index": 62.0,
        "fear_greed_label": "贪婪",
        "trade_date": "20250613",
    }
    service = MagicMock()
    service.engine.bar_service.get_return.return_value = {"return_pct": 8.5}

    ctx = build_team_market_context(
        service,
        _sample_item(),
        diagnose={"quote": {"industry": "白酒"}},
    )

    assert ctx["provider"] == "zak-market-context-v1"
    assert ctx["stock_vs_benchmark"]["excess_pct"] == 3.5
    assert any("沪深300" in line for line in ctx["summary_lines"])
    assert any("恐贪" in line for line in ctx["summary_lines"])
    assert ctx["sector"]["industry"] == "白酒"


@patch("vnpy_ashare.services.analysis_detail.market_context.fetch_market_sentiment", return_value=None)
@patch("vnpy_ashare.services.analysis_detail.market_context._load_sector_ranks")
@patch("vnpy_ashare.services.analysis_detail.market_context.get_market_quotes_cache")
@patch("vnpy_ashare.services.analysis_detail.market_context.get_market_overview_context")
@patch("vnpy_ashare.services.analysis_detail.market_context.resolve_benchmark_return_pct", return_value=-2.0)
@patch("vnpy_ashare.services.analysis_detail.market_context.compute_relative_index_excess", return_value=1.0)
def test_build_team_market_context_uses_overview_cache(
    _mock_excess: MagicMock,
    _mock_bench: MagicMock,
    mock_overview: MagicMock,
    mock_quotes: MagicMock,
    mock_sector_ranks: MagicMock,
    _mock_sentiment: MagicMock,
):
    mock_overview.return_value = {
        "index_lines": ["沪深300 3800.00 +0.50%"],
        "breadth_line": "广度：涨 2800 / 跌 1200 / 平 100",
        "environment_line": "环境：恐贪 55 中性",
        "sector_lines": ["白酒 均涨 +1.20%（12 只）"],
    }
    mock_quotes.return_value = [{"vt_symbol": "600519.SSE", "change_pct": 1.0}]
    mock_sector_ranks.return_value = [
        SectorRankItem(industry="白酒", count=12, avg_change_pct=1.2),
        SectorRankItem(industry="银行", count=20, avg_change_pct=0.5),
    ]

    service = MagicMock()
    service.engine.bar_service.get_return.return_value = {"return_pct": 4.0}

    ctx = build_team_market_context(service, _sample_item(), diagnose={"quote": {"industry": "白酒"}})

    assert ctx["overview"]["source"] == "market_page_cache"
    assert ctx["sector"]["rank"] == 1
    assert "广度" in "；".join(ctx["summary_lines"])
