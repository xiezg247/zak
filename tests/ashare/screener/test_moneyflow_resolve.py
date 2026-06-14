"""资金流统一解析测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot
from vnpy_ashare.screener.dimensions.moneyflow_resolve import resolve_moneyflow_hits


def test_resolve_moneyflow_intraday_prefers_mcp_over_tushare() -> None:
    snapshot = MarketQuotesSnapshot(
        rows=[{"vt_symbol": "600000.SSE", "change_pct": 1.0, "amount": 1e8}],
        updated_at="x",
        total=1,
    )

    with (
        patch("vnpy_ashare.screener.dimensions.moneyflow_resolve.is_ashare_trading_session", return_value=True),
        patch(
            "vnpy_ashare.screener.dimensions.moneyflow_resolve.load_screening_quote_snapshot",
            return_value=snapshot,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.moneyflow_resolve.fetch_intraday_moneyflow_map",
            return_value={"600000.SSE": 500.0},
        ),
        patch(
            "vnpy_ashare.screener.dimensions.moneyflow_resolve.fetch_moneyflow_with_fallback",
        ) as mock_tushare,
    ):
        hits, total, trade_date = resolve_moneyflow_hits(5, weight=1.0)

    mock_tushare.assert_not_called()
    assert trade_date == ""
    assert total == 1
    assert len(hits) == 1
    assert hits[0].dimension_id == "moneyflow_intraday"
    assert hits[0].row["net_mf_amount"] == 500.0


def test_resolve_moneyflow_post_close_uses_tushare() -> None:
    snapshot = MarketQuotesSnapshot(rows=[], updated_at="x", total=0)

    with (
        patch("vnpy_ashare.screener.dimensions.moneyflow_resolve.is_ashare_trading_session", return_value=False),
        patch(
            "vnpy_ashare.screener.dimensions.moneyflow_resolve.load_screening_quote_snapshot",
            return_value=snapshot,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.moneyflow_resolve.fetch_intraday_moneyflow_map",
        ) as mock_mcp,
        patch(
            "vnpy_ashare.screener.dimensions.moneyflow_resolve.fetch_moneyflow_with_fallback",
            return_value=(
                [
                    {
                        "vt_symbol": "600000.SSE",
                        "symbol": "600000",
                        "name": "浦发银行",
                        "net_mf_amount": 800,
                        "buy_elg_amount": 500,
                        "sell_elg_amount": 100,
                        "buy_lg_amount": 400,
                        "sell_lg_amount": 200,
                        "buy_md_amount": 100,
                        "sell_md_amount": 50,
                    }
                ],
                "20260612",
            ),
        ),
    ):
        hits, total, trade_date = resolve_moneyflow_hits(5, weight=1.0)

    mock_mcp.assert_not_called()
    assert trade_date == "20260612"
    assert total == 1
    assert len(hits) == 1
    assert hits[0].dimension_id == "moneyflow"


def test_build_moneyflow_source_subtitle_variants() -> None:
    from vnpy_ashare.screener.dimensions.base import DimensionHit
    from vnpy_ashare.screener.dimensions.moneyflow_resolve import build_moneyflow_source_subtitle

    assert build_moneyflow_source_subtitle([], "") == ""
    assert build_moneyflow_source_subtitle([], "20260612") == " · Tushare 20260612"

    mcp_hit = DimensionHit(
        vt_symbol="600000.SSE",
        dimension_id="moneyflow_intraday",
        label="盘中资金",
        weight=1.0,
        score=90.0,
        reason="盘中资金：主力净流入 500 万",
        row={"net_mf_amount": 500},
    )
    assert build_moneyflow_source_subtitle([mcp_hit], "") == " · MCP 盘中"

    proxy_hit = DimensionHit(
        vt_symbol="600000.SSE",
        dimension_id="moneyflow_intraday",
        label="盘中资金",
        weight=1.0,
        score=50.0,
        reason="盘中资金：涨幅 +2%（代理）",
        row={"moneyflow_proxy": True},
    )
    assert build_moneyflow_source_subtitle([proxy_hit], "") == " · 成交额代理"
