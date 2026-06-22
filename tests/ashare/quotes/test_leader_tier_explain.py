"""explain_leader_tier 解读测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.analysis.leader_tier import explain_leader_tier_for_symbol
from vnpy_ashare.quotes.radar.radar_leader import (
    compute_leader_score_breakdown,
    rank_sector_group_full,
    tier_for_group_rank,
)


class LeaderTierExplainTest(unittest.TestCase):
    def test_tier_for_group_rank_matches_leader_rules(self) -> None:
        self.assertEqual(tier_for_group_rank(0, leader_score=50), "dragon_1")
        self.assertEqual(tier_for_group_rank(1, leader_score=50), "dragon_2")
        self.assertEqual(tier_for_group_rank(2, leader_score=40, max_per_sector=8), "follower")
        self.assertEqual(tier_for_group_rank(2, leader_score=30, max_per_sector=8), "")

    def test_rank_sector_group_full_orders_by_score(self) -> None:
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "name": "龙一候选",
                "industry": "半导体",
                "change_pct": 10.0,
                "amount": 3e8,
                "limit_times": 3,
                "net_mf_amount": 2e7,
                "symbol": "600000",
            },
            {
                "vt_symbol": "000001.SZSE",
                "name": "龙二候选",
                "industry": "半导体",
                "change_pct": 9.5,
                "amount": 2e8,
                "limit_times": 2,
                "net_mf_amount": 1e7,
                "symbol": "000001",
            },
        ]
        ranked = rank_sector_group_full(rows, sector_name="半导体", include_breakdown=True)
        self.assertEqual(ranked[0]["leader_tier"], "dragon_1")
        self.assertEqual(ranked[1]["leader_tier"], "dragon_2")
        self.assertIn("score_breakdown", ranked[0])

    def test_compute_leader_score_breakdown_has_components(self) -> None:
        row = {
            "vt_symbol": "600000.SSE",
            "change_pct": 10.0,
            "amount": 2e8,
            "limit_times": 2,
            "net_mf_amount": 1e7,
            "symbol": "600000",
        }
        breakdown = compute_leader_score_breakdown(row, amount_rank=0.8, max_net_mf=1e7)
        self.assertGreater(float(breakdown["leader_score"]), 0)
        self.assertEqual(len(breakdown["components"]), 7)

    @patch("vnpy_ashare.quotes.analysis.leader_tier.load_screening_quote_snapshot")
    @patch("vnpy_ashare.quotes.analysis.leader_tier.attach_sector_fields")
    @patch("vnpy_ashare.quotes.analysis.leader_tier.attach_first_time_fields")
    @patch("vnpy_ashare.quotes.analysis.leader_tier.get_cached_limit_times_map")
    def test_explain_leader_tier_for_symbol(
        self,
        mock_limit_map,
        mock_attach_first_time,
        mock_attach_sector,
        mock_load_snapshot,
    ) -> None:
        mock_limit_map.return_value = {}
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "name": "龙头A",
                "industry": "半导体",
                "change_pct": 10.0,
                "amount": 3e8,
                "limit_times": 3,
                "net_mf_amount": 2e7,
                "symbol": "600000",
            },
            {
                "vt_symbol": "000001.SZSE",
                "name": "龙头B",
                "industry": "半导体",
                "change_pct": 9.5,
                "amount": 2e8,
                "limit_times": 2,
                "net_mf_amount": 1e7,
                "symbol": "000001",
            },
        ]

        class _Snapshot:
            pass

        snapshot = _Snapshot()
        snapshot.rows = rows
        mock_load_snapshot.return_value = snapshot
        mock_attach_sector.return_value = (rows, [])
        mock_attach_first_time.side_effect = lambda peer_rows: None

        result = explain_leader_tier_for_symbol("600000.SSE")
        self.assertEqual(result["leader_tier"], "dragon_1")
        self.assertEqual(result["leader_tier_label"], "龙一")
        self.assertEqual(result["sector"], "半导体")
        self.assertIn("summary", result)
        self.assertIn("score_breakdown", result)
        self.assertGreaterEqual(len(result["reasons"]), 1)

        result_b = explain_leader_tier_for_symbol("000001.SZSE")
        self.assertEqual(result_b["leader_tier"], "dragon_2")
        self.assertEqual(result_b["peers_ahead"][0]["vt_symbol"], "600000.SSE")


if __name__ == "__main__":
    unittest.main()
