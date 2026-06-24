"""投研团队数据预取与财务聚合测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy_ashare.services.analysis_detail.team_facts import (
    build_financial_extras,
    prefetch_team_facts,
    snapshot_row_to_dict,
)
from vnpy_ashare.storage.repositories.financial import FinancialSnapshotRow


def _sample_row() -> FinancialSnapshotRow:
    return FinancialSnapshotRow(
        ts_code="600519.SH",
        end_date="20241231",
        revenue=100.0,
        net_income=50.0,
        roe=20.0,
        gross_margin=55.0,
        net_income_yoy=12.0,
        debt_ratio=35.0,
        current_ratio=2.1,
    )


def test_snapshot_row_to_dict():
    data = snapshot_row_to_dict(_sample_row())
    assert data["roe"] == 20.0
    assert data["end_date"] == "20241231"


@patch("vnpy_ashare.services.analysis_detail.team_facts.lookup_daily_basic")
@patch("vnpy_ashare.services.analysis_detail.team_facts.list_snapshots")
def test_build_financial_extras_merges_sources(mock_list: MagicMock, mock_lookup: MagicMock):
    mock_list.return_value = [_sample_row()]
    mock_lookup.return_value = {"pe_ttm": 25.0, "pb": 8.0, "trade_date": "20250613"}

    extras = build_financial_extras("600519.SH", "600519.SSE")

    assert extras["latest_financials"]["roe"] == 20.0
    assert extras["valuation"]["pe_ttm"] == 25.0
    assert extras["data_availability"]["roe"] is True
    assert extras["data_availability"]["pe_ttm"] is True


@patch("vnpy_ashare.services.analysis_detail.team_facts.list_snapshots", return_value=[])
@patch("vnpy_ashare.services.analysis_detail.team_facts.lookup_daily_basic", return_value=None)
def test_build_financial_extras_empty(_mock_list: MagicMock, _mock_lookup: MagicMock):
    extras = build_financial_extras("600519.SH", "600519.SSE")
    assert extras["latest_financials"] is None
    assert extras["data_availability"]["roe"] is False
    assert "暂无" in extras["note"]


@patch("vnpy_ashare.services.analysis_detail.team_facts.build_team_market_context")
def test_prefetch_team_facts_parallel(mock_market: MagicMock):
    mock_market.return_value = {"summary_lines": ["沪深300 近60日 +5.00%"]}
    service = MagicMock()
    service.get_diagnose_result.return_value = None
    service.analyze_financial.return_value = {"symbol": "600519.SSE", "roe": 20}
    service.analyze_risk.return_value = {"volatility_annualized_pct": 22.0}
    service.analyze_strategy.return_value = {"technical": {"ma_alignment": "多头"}}

    result = prefetch_team_facts(service, "600519")

    assert result["symbol"] == "600519.SSE"
    assert "financial" in result
    assert "risk" in result
    assert "strategy" in result
    assert "market_context" in result
    assert result["market_context"]["summary_lines"]
    service.analyze_financial.assert_called_once_with("600519")
    service.analyze_risk.assert_called_once_with("600519")
    service.analyze_strategy.assert_called_once_with("600519")


def test_prefetch_team_facts_invalid_symbol():
    service = MagicMock()
    result = prefetch_team_facts(service, "INVALID")
    assert "error" in result
    service.analyze_financial.assert_not_called()


@patch("vnpy_ashare.services.analysis_detail.team_facts.build_team_market_context", return_value={"summary_lines": []})
def test_prefetch_enriches_financial_from_diagnose_cache(_mock_market: MagicMock):
    service = MagicMock()
    service.get_diagnose_result.return_value = {
        "symbol": "600519.SSE",
        "as_of": "2026-06-16 10:00:00",
        "technical": {"fields": {"MACD.MACD": "1.2", "RSI": "55"}},
        "fundamental": {"fields": {"市盈(TTM)": "28.5", "ROE": "22.1"}},
        "capital_flow": {"fields": {"主力净流入": "1.5亿"}},
        "quote": {"industry": "白酒"},
    }
    service.analyze_financial.return_value = {
        "symbol": "600519.SSE",
        "valuation": {},
        "latest_financials": None,
        "data_availability": {"pe_ttm": False, "roe": False},
    }
    service.analyze_risk.return_value = {"volatility_annualized_pct": 22.0}
    service.analyze_strategy.return_value = {"technical": {"ma_alignment": "多头"}}

    result = prefetch_team_facts(service, "600519")

    assert result["diagnose"]["available"] is True
    assert result["financial"]["valuation"]["pe_ttm"] == 28.5
    assert result["financial"]["latest_financials"]["roe"] == 22.1
    assert "macd" in result["strategy"]["diagnose_indicators"]


@patch("vnpy_ashare.services.analysis_detail.team_facts.build_team_market_context", return_value={"summary_lines": []})
def test_prefetch_fetches_diagnose_when_cache_miss(_mock_market: MagicMock):
    service = MagicMock()
    service.get_diagnose_result.return_value = None
    service.analyze_financial.return_value = {"symbol": "600519.SSE", "valuation": {}}
    service.analyze_risk.return_value = {}
    service.analyze_strategy.return_value = {}
    service.diagnose.return_value = {
        "symbol": "600519.SSE",
        "as_of": "2026-06-16",
        "fundamental": {"fields": {"市盈(TTM)": "30"}},
        "technical": {},
        "capital_flow": {},
        "quote": {},
    }

    result = prefetch_team_facts(service, "600519")

    service.diagnose.assert_called_once_with("600519")
    service.set_diagnose_result.assert_called_once()
    assert result["diagnose"]["available"] is True
    assert result["diagnose"]["source"] == "diagnose_stock"


@patch("vnpy_ashare.services.analysis_detail.team_facts.build_team_market_context", return_value={"summary_lines": []})
def test_prefetch_fetches_diagnose_when_cache_symbol_mismatch(_mock_market: MagicMock):
    service = MagicMock()
    service.get_diagnose_result.return_value = {"symbol": "002230.SZSE"}
    service.analyze_financial.return_value = {"symbol": "600519.SSE", "valuation": {}}
    service.analyze_risk.return_value = {}
    service.analyze_strategy.return_value = {}
    service.diagnose.return_value = {
        "symbol": "600519.SSE",
        "fundamental": {"fields": {"市盈(TTM)": "28"}},
        "technical": {},
        "capital_flow": {},
        "quote": {},
    }

    result = prefetch_team_facts(service, "600519")

    service.diagnose.assert_called_once_with("600519")
    assert result["diagnose"]["available"] is True
    assert result["diagnose"]["source"] == "diagnose_stock"
