"""龙头评分与情绪调制测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle
from vnpy_ashare.quotes.market.emotion_cycle_inputs import EmotionCycleInputs
from vnpy_ashare.quotes.radar.radar_leader import compute_leader_score, rank_sector_leaders
from vnpy_ashare.screener.sentiment.sentiment_gate import apply_emotion_modulation, apply_sentiment_modulation


class LeaderScoreTest(unittest.TestCase):
    def test_higher_limit_times_scores_higher(self) -> None:
        base = {
            "vt_symbol": "600000.SSE",
            "change_pct": 10.0,
            "amount": 2e8,
            "net_mf_amount": 1e7,
            "symbol": "600000",
        }
        low = compute_leader_score({**base, "limit_times": 1}, amount_rank=0.8, max_net_mf=1e7)
        high = compute_leader_score({**base, "limit_times": 5}, amount_rank=0.8, max_net_mf=1e7)
        self.assertGreater(high, low)

    def test_rank_sector_leaders_assigns_tiers(self) -> None:
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "industry": "半导体",
                "change_pct": 10.0,
                "amount": 3e8,
                "limit_times": 3,
                "net_mf_amount": 2e7,
                "symbol": "600000",
            },
            {
                "vt_symbol": "000001.SZSE",
                "industry": "半导体",
                "change_pct": 9.5,
                "amount": 2e8,
                "limit_times": 2,
                "net_mf_amount": 1e7,
                "symbol": "000001",
            },
        ]
        ranked = rank_sector_leaders(rows)
        self.assertEqual(ranked[0].leader_tier, "dragon_1")
        self.assertEqual(ranked[1].leader_tier, "dragon_2")


class EmotionModulationTest(unittest.TestCase):
    def test_emotion_modulation_scales_score(self) -> None:
        snap = classify_emotion_cycle(
            EmotionCycleInputs(
                limit_up_count=55,
                limit_down_count=3,
                up_ratio=0.5,
                total_amount=2e12,
                max_limit_times=4,
                limit_ladder_depth=2,
            ),
        )
        rows = [{"vt_symbol": "600000.SSE", "composite_score": 80.0, "hit_reasons": ["动量"]}]
        adjusted, meta = apply_emotion_modulation(rows, snapshot=snap)
        self.assertLess(adjusted[0]["composite_score"], 80.0)
        self.assertIn("emotion_stage", meta or {})

    def test_recession_caps_top_three(self) -> None:
        snap = classify_emotion_cycle(
            EmotionCycleInputs(
                limit_up_count=10,
                limit_down_count=25,
                up_ratio=0.2,
                total_amount=2e12,
                max_limit_times=1,
                limit_ladder_depth=0,
            ),
        )
        rows = [
            {"vt_symbol": f"60000{i}.SSE", "composite_score": 90 - i * 5, "hit_reasons": []}
            for i in range(5)
        ]
        adjusted, meta = apply_emotion_modulation(rows, snapshot=snap)
        self.assertEqual(len(adjusted), 3)
        self.assertTrue(meta and meta.get("emotion_capped"))

    @patch("vnpy_ashare.screener.sentiment.sentiment_gate.try_fetch_fear_greed_index", return_value=None)
    @patch("vnpy_ashare.screener.sentiment.sentiment_gate.try_load_emotion_cycle_snapshot")
    @patch("vnpy_ashare.screener.sentiment.sentiment_gate.sentiment_gate_enabled", return_value=True)
    def test_sentiment_modulation_applies_emotion_when_no_fear_greed(
        self,
        _enabled,
        mock_cycle,
        _fg,
    ) -> None:
        snap = classify_emotion_cycle(
            EmotionCycleInputs(
                limit_up_count=55,
                limit_down_count=3,
                up_ratio=0.5,
                total_amount=2e12,
                max_limit_times=4,
                limit_ladder_depth=2,
            ),
        )
        mock_cycle.return_value = snap
        rows = [{"vt_symbol": "600000.SSE", "composite_score": 80.0, "hit_reasons": [], "dimensions": {}}]
        adjusted, meta = apply_sentiment_modulation(rows)
        self.assertLess(adjusted[0]["composite_score"], 80.0)
        self.assertIn("emotion_stage", meta or {})
