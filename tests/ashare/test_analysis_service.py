"""tdx_diagnose 与 AnalysisService.diagnose 单元测试。"""

from __future__ import annotations

import json
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


def _wenda_payload(**extra_fields: str) -> str:
    headers = ["sec_code", "sec_name", "now_price", "chg", *extra_fields.keys()]
    row = ["600000", "浦发银行", "10.5", "1.2", *extra_fields.values()]
    return json.dumps({"headers": headers, "data": [row]}, ensure_ascii=False)


@pytest.fixture
def analysis_service():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "packages/vnpy-ashare/vnpy_ashare/services/analysis_service.py"
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


def test_diagnose_with_mock_wenda(analysis_service):
    def _execute(name: str, args: dict) -> str:
        question = args.get("question", "")
        if "MACD" in question:
            return _wenda_payload(**{"MACD.MACD": "-0.5", "MACD.DIF": "-0.3", "MACD.DEA": "-0.1"})
        if "市盈率" in question:
            return _wenda_payload(**{"市盈(动)": "8.5", "加权净资产收益率(ROE)": "12.3"})
        if "主力" in question:
            return _wenda_payload(**{"主力净额": "12345678"})
        return _wenda_payload()

    analysis_service.bind_mcp(_execute, ["mcp_tdx_tdx_wenda_quotes"])
    result = analysis_service.diagnose("600000.SSE", include_reports=False)
    assert result["symbol"] == "600000.SSE"
    assert result["quote"]["last_price"] == 10.5
    assert result["technical"]["macd"] == -0.5
    assert result["fundamental"]["pe_ttm"] == 8.5
    assert result["capital_flow"]["main_net"] == 12345678.0
    assert "tdx_mcp" in result["sources"]


def test_pick_mcp_tool(analysis_service):
    analysis_service.bind_mcp(None, ["mcp_tdx_tdx_wenda_quotes", "mcp_tdx_stock_quotes"])
    name = analysis_service._pick_mcp_tool(("report", "research"))
    assert name is None


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


def test_parse_wenda_table():
    from vnpy_ashare.services.tdx_diagnose import _parse_wenda_table

    raw = json.dumps(
        {
            "headers": ["sec_name", "now_price", "MACD.MACD<br>2026.06.08"],
            "data": [["测试股", "12.34", "-0.88"]],
        },
        ensure_ascii=False,
    )
    parsed = _parse_wenda_table(raw)
    assert parsed["fields"]["sec_name"] == "测试股"
    assert parsed["fields"]["MACD.MACD"] == "-0.88"
