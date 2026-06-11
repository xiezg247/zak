"""tdx_diagnose 与 AnalysisService.diagnose 单元测试。"""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from types import SimpleNamespace

from vnpy_ashare.services.analysis_service import AnalysisService


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


class AnalysisServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = SimpleNamespace(
            bar_service=_FakeBarService(),
            main_engine=SimpleNamespace(),
            event_engine=SimpleNamespace(),
        )
        self.service = AnalysisService(engine)

    def test_technical_snapshot(self) -> None:
        result = self.service.technical_snapshot("600000.SSE", lookback=20)
        self.assertEqual(result["symbol"], "600000.SSE")
        self.assertIsNotNone(result["ma"]["ma5"])
        self.assertIn("ma_alignment", result)
        self.assertEqual(result["period_return"]["return_pct"], 5.5)

    def test_diagnose_with_mock_wenda(self) -> None:
        def _execute(name: str, args: dict) -> str:
            question = args.get("question", "")
            if "MACD" in question:
                return _wenda_payload(**{"MACD.MACD": "-0.5", "MACD.DIF": "-0.3", "MACD.DEA": "-0.1"})
            if "市盈率" in question:
                return _wenda_payload(**{"市盈(动)": "8.5", "加权净资产收益率(ROE)": "12.3"})
            if "主力" in question:
                return _wenda_payload(**{"主力净额": "12345678"})
            return _wenda_payload()

        self.service.bind_mcp(_execute, ["mcp_tdx_tdx_wenda_quotes"])
        result = self.service.diagnose("600000.SSE", include_reports=False)
        self.assertEqual(result["symbol"], "600000.SSE")
        self.assertEqual(result["quote"]["last_price"], 10.5)
        self.assertEqual(result["technical"]["macd"], -0.5)
        self.assertEqual(result["fundamental"]["pe_ttm"], 8.5)
        self.assertEqual(result["capital_flow"]["main_net"], 12345678.0)
        self.assertIn("tdx_mcp", result["sources"])

    def test_pick_mcp_tool(self) -> None:
        self.service.bind_mcp(None, ["mcp_tdx_tdx_wenda_quotes", "mcp_tdx_stock_quotes"])
        name = self.service._pick_mcp_tool(("report", "research"))
        self.assertIsNone(name)

    def test_strategy_signals(self) -> None:
        result = self.service.strategy_signals("600000.SSE")
        self.assertEqual(result["strategy"], "AshareDoubleMaStrategy")
        self.assertIsNotNone(result["current"]["fast_ma"])
        self.assertIn("disclaimer", result)

    def test_historical_pattern_summary(self) -> None:
        result = self.service.historical_pattern_summary("600000.SSE", lookback=20)
        self.assertEqual(result["symbol"], "600000.SSE")
        self.assertIn("return_pct", result)
        self.assertIn("pattern_label", result)
        self.assertIn("disclaimer", result)


class TdxDiagnoseParseTests(unittest.TestCase):
    def test_parse_wenda_table(self) -> None:
        from vnpy_ashare.services.tdx_diagnose import _parse_wenda_table

        raw = json.dumps(
            {
                "headers": ["sec_name", "now_price", "MACD.MACD<br>2026.06.08"],
                "data": [["测试股", "12.34", "-0.88"]],
            },
            ensure_ascii=False,
        )
        parsed = _parse_wenda_table(raw)
        self.assertEqual(parsed["fields"]["sec_name"], "测试股")
        self.assertEqual(parsed["fields"]["MACD.MACD"], "-0.88")


if __name__ == "__main__":
    unittest.main()
