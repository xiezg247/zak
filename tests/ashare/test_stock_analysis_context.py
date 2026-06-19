"""个股分析上下文服务单元测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.stock.short_term import ShortTermProfile
from vnpy_ashare.services.stock.context import (
    build_analysis_ai_context,
    build_financial_quality_hints,
    extract_diagnose_metrics,
    format_technical_summary,
)
from vnpy_ashare.storage.repositories.financial import FinancialSnapshotRow


class StockAnalysisContextTests(unittest.TestCase):
    def test_extract_diagnose_metrics(self) -> None:
        diagnose = {
            "technical": {
                "macd": 0.12,
                "dif": 0.08,
                "dea": 0.05,
                "kdj_k": 55.0,
                "kdj_d": 50.0,
                "kdj_j": 65.0,
                "rsi": 62.5,
                "fields": {},
            },
            "fundamental": {"pe_ttm": 18.5, "roe": 12.3, "fields": {}},
            "capital_flow": {"main_net": 12345678.0, "fields": {}},
            "quote": {"industry": "@白酒@"},
        }
        metrics = extract_diagnose_metrics(diagnose)
        self.assertEqual(metrics.macd, 0.12)
        self.assertEqual(metrics.kdj_k, 55.0)
        self.assertEqual(metrics.rsi, 62.5)
        self.assertEqual(metrics.pe_ttm, 18.5)
        self.assertEqual(metrics.roe, 12.3)
        self.assertEqual(metrics.main_net, 12345678.0)
        self.assertEqual(metrics.industry, "白酒")

    def test_format_technical_summary_with_relative_returns(self) -> None:
        text = format_technical_summary(
            {
                "as_of": "2024-06-01",
                "last_close": 10.5,
                "ma": {"ma5": 10, "ma10": 9.8, "ma20": 9.5, "ma60": 9.0},
                "ma_alignment": "多头排列",
                "volume_ratio_5d": 1.2,
                "period_return": {"return_pct": 5.5},
            },
            relative_returns={"ret_5d": 2.0, "ret_20d": 8.0, "rs_20d": 3.5},
        )
        self.assertIn("多头排列", text)
        self.assertIn("相对沪深300(20日) +3.50%", text)

    def test_financial_quality_hints(self) -> None:
        snapshots = [
            FinancialSnapshotRow(
                ts_code="600519.SH",
                end_date="20231231",
                revenue_yoy=-12.0,
                net_income_yoy=-25.0,
                debt_ratio=75.0,
                ocf_to_profit=0.3,
            )
        ]
        hints = build_financial_quality_hints(snapshots)
        self.assertTrue(any("现金含量偏低" in item for item in hints))
        self.assertTrue(any("杠杆偏高" in item for item in hints))

    def test_build_analysis_ai_context_short_term(self) -> None:
        payload = type(
            "Payload",
            (),
            {
                "technical": {},
                "short_term": ShortTermProfile(
                    ts_code="600519.SH",
                    vt_symbol="600519.SSE",
                    limit_times=3,
                    leader_tier_label="龙一",
                    seal_strength_label="强",
                    entry_mode={"recommended_label": "打板", "emotion_stage_label": "启动"},
                ),
            },
        )()
        text = build_analysis_ai_context(payload)
        self.assertIn("短线：", text)
        self.assertIn("连板 3", text)
        self.assertIn("龙一", text)
        self.assertIn("打板", text)


if __name__ == "__main__":
    unittest.main()
