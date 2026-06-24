"""chart_notes 与 valuation chart 测试。"""

from __future__ import annotations

import json
import unittest

from vnpy_common.ai.chart_notes import format_chart_attachments_appendix, merge_report_body_with_charts
from vnpy_common.ai.protocol import AiChartBar, AiChartSpec
from vnpy_ashare.services.note import build_report_context_json
from vnpy_ashare.services.stock.valuation_chart import build_valuation_chart_series
from vnpy_llm.tools.chart_collector import try_collect_charts


class ChartNotesTests(unittest.TestCase):
    def test_parse_charts_from_context_json(self) -> None:
        from vnpy_common.ai.chart_notes import parse_charts_from_context_json

        payload = {
            "scope": "ai_chat",
            "summary": "test",
            "charts": [
                {
                    "chart_id": "c1",
                    "kind": "candlestick",
                    "symbol": "600519.SSE",
                    "series": [],
                }
            ],
        }
        charts = parse_charts_from_context_json(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0].symbol, "600519.SSE")

    def test_format_appendix(self) -> None:
        charts = [
            AiChartSpec(
                chart_id="c1",
                kind="candlestick",
                symbol="600519.SSE",
                caption="600519.SSE · 近30根日K",
                series=[],
            )
        ]
        text = format_chart_attachments_appendix(charts)
        self.assertIn("附：本轮图表", text)
        self.assertIn("600519.SSE", text)

    def test_merge_report_body(self) -> None:
        charts = [
            AiChartSpec(
                chart_id="c1",
                kind="line",
                symbol="600519.SSE",
                caption="PE(TTM)",
                series=[],
            )
        ]
        merged = merge_report_body_with_charts("正文", charts)
        self.assertIn("正文", merged)
        self.assertIn("PE(TTM)", merged)

    def test_context_json_includes_charts(self) -> None:
        charts = [
            AiChartSpec(
                chart_id="c1",
                kind="line",
                symbol="600519.SSE",
                series=[],
            )
        ]
        payload = json.loads(build_report_context_json(scope="ai_chat", summary="test", charts=charts))
        self.assertEqual(len(payload["charts"]), 1)


class AnalyzeFinancialChartTests(unittest.TestCase):
    def test_collect_pe_and_pb_charts(self) -> None:
        payload = {
            "symbol": "600519.SSE",
            "name": "贵州茅台",
            "valuation_pe_series": [{"date": "2026-06-01", "value": 25.0}],
            "valuation_pb_series": [{"date": "2026-06-01", "value": 8.5}],
        }
        charts = try_collect_charts("analyze_financial", json.dumps(payload, ensure_ascii=False), success=True)
        self.assertEqual(len(charts), 2)
        keys = {chart.chart_key for chart in charts}
        self.assertIn("valuation:pe:600519.SSE", keys)
        self.assertIn("valuation:pb:600519.SSE", keys)


class ValuationChartSeriesTests(unittest.TestCase):
    def test_empty_history(self) -> None:
        series = build_valuation_chart_series("__missing__")
        self.assertEqual(series["pe_ttm"], [])
        self.assertEqual(series["pb"], [])


if __name__ == "__main__":
    unittest.main()
