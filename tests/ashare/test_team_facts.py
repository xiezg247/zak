"""投研团队数据预取与财务聚合测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy_ashare.services.analysis.team_facts import (
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


@patch("vnpy_ashare.services.analysis.team_facts.lookup_daily_basic")
@patch("vnpy_ashare.services.analysis.team_facts.list_snapshots")
def test_build_financial_extras_merges_sources(mock_list: MagicMock, mock_lookup: MagicMock):
    mock_list.return_value = [_sample_row()]
    mock_lookup.return_value = {"pe_ttm": 25.0, "pb": 8.0, "trade_date": "20250613"}

    extras = build_financial_extras("600519.SH", "600519.SSE")

    assert extras["latest_financials"]["roe"] == 20.0
    assert extras["valuation"]["pe_ttm"] == 25.0
    assert extras["data_availability"]["roe"] is True
    assert extras["data_availability"]["pe_ttm"] is True


@patch("vnpy_ashare.services.analysis.team_facts.list_snapshots", return_value=[])
@patch("vnpy_ashare.services.analysis.team_facts.lookup_daily_basic", return_value=None)
def test_build_financial_extras_empty(_mock_list: MagicMock, _mock_lookup: MagicMock):
    extras = build_financial_extras("600519.SH", "600519.SSE")
    assert extras["latest_financials"] is None
    assert extras["data_availability"]["roe"] is False
    assert "暂无" in extras["note"]


def test_prefetch_team_facts_parallel():
    service = MagicMock()
    service.analyze_financial.return_value = {"symbol": "600519.SSE", "roe": 20}
    service.analyze_risk.return_value = {"volatility_annualized_pct": 22.0}
    service.analyze_strategy.return_value = {"technical": {"ma_alignment": "多头"}}

    result = prefetch_team_facts(service, "600519")

    assert result["symbol"] == "600519.SSE"
    assert "financial" in result
    assert "risk" in result
    assert "strategy" in result
    service.analyze_financial.assert_called_once_with("600519")
    service.analyze_risk.assert_called_once_with("600519")
    service.analyze_strategy.assert_called_once_with("600519")


def test_prefetch_team_facts_invalid_symbol():
    service = MagicMock()
    result = prefetch_team_facts(service, "INVALID")
    assert "error" in result
    service.analyze_financial.assert_not_called()
