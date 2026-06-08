"""AnalysisService 单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest


class _FakeBar:
    def __init__(self, day: int, price: float) -> None:
        self.datetime = datetime(2024, 1, day)
        self.close_price = price
        self.high_price = price + 0.05
        self.low_price = price - 0.05
        self.volume = 1000 + day * 10


class _FakeBarService:
    def load_bars(self, symbol, exchange, scope="daily", start=None, end=None):
        bars = []
        price = 10.0
        for day in range(1, 31):
            bars.append(_FakeBar(day, price))
            price += 0.1
        return bars

    def get_return(self, symbol, exchange, scope="daily", lookback_days=20):
        return {
            "symbol": f"{symbol}.{getattr(exchange, 'value', exchange)}",
            "return_pct": 5.5,
            "lookback_days": lookback_days,
        }


@pytest.fixture
def analysis_service():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "vnpy_ashare/services/analysis_service.py"
    spec = importlib.util.spec_from_file_location("analysis_service_mod", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    engine = SimpleNamespace(
        bar_service=_FakeBarService(),
        main_engine=SimpleNamespace(),
        event_engine=SimpleNamespace(),
    )
    return mod.AnalysisService(engine)


def test_technical_snapshot(analysis_service):
    result = analysis_service.technical_snapshot("600000.SSE", lookback=20)
    assert result["symbol"] == "600000.SSE"
    assert result["ma"]["ma5"] is not None
    assert "ma_alignment" in result
    assert result["period_return"]["return_pct"] == 5.5


def test_diagnose_with_mock_mcp(analysis_service):
    import json

    payload = {
        "reports": [
            {
                "title": "测试研报",
                "broker": "测试券商",
                "date": "2025-06-01",
                "rating": "买入",
                "summary": "示例摘要",
            }
        ]
    }
    analysis_service.bind_mcp(
        lambda name, args: json.dumps(payload, ensure_ascii=False),
        ["mcp_tdx_research_report"],
    )
    result = analysis_service.diagnose("600000.SSE")
    assert result["symbol"] == "600000.SSE"
    assert len(result["reports"]) == 1
    assert result["reports"][0]["broker"] == "测试券商"
    assert "tdx_mcp" in result["sources"]


def test_pick_mcp_tool(analysis_service):
    analysis_service.bind_mcp(None, ["mcp_tdx_stock_quotes", "mcp_tdx_research_report"])
    name = analysis_service._pick_mcp_tool(("report", "research"))
    assert name == "mcp_tdx_research_report"


def test_strategy_signals(analysis_service):
    result = analysis_service.strategy_signals("600000.SSE")
    assert result["strategy"] == "AshareDoubleMaStrategy"
    assert result["current"]["fast_ma"] is not None
    assert "disclaimer" in result


def test_historical_pattern_summary(analysis_service):
    result = analysis_service.historical_pattern_summary("600000.SSE", lookback=20)
    assert result["symbol"] == "600000.SSE"
    assert "return_pct" in result
    assert "pattern_label" in result
    assert "disclaimer" in result
