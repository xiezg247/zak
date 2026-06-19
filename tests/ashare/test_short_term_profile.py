"""个股短线画像单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.services.stock.short_term import build_short_term_profile


class ShortTermProfileTests(unittest.TestCase):
    @patch("vnpy_ashare.services.stock.short_term.assess_regulatory_deviation_for_vt_symbol")
    @patch("vnpy_ashare.services.stock.short_term.load_emotion_cycle_snapshot")
    @patch("vnpy_ashare.services.stock.short_term.evaluate_entry_mode")
    @patch("vnpy_ashare.services.stock.short_term._resolve_sector_leaders")
    @patch("vnpy_ashare.services.stock.short_term.attach_seal_reopen_fields")
    @patch("vnpy_ashare.services.stock.short_term.get_cached_limit_times_map")
    @patch("vnpy_ashare.services.stock.short_term.resolve_limit_times")
    @patch("vnpy_ashare.services.stock.short_term._find_limit_today")
    @patch("vnpy_ashare.services.stock.short_term._merge_quote_row")
    def test_build_short_term_profile(
        self,
        mock_merge: MagicMock,
        mock_limit: MagicMock,
        mock_resolve_boards: MagicMock,
        mock_limit_map: MagicMock,
        _mock_seal: MagicMock,
        mock_leaders: MagicMock,
        mock_entry: MagicMock,
        _mock_cycle: MagicMock,
        _mock_reg: MagicMock,
    ) -> None:
        mock_merge.return_value = {
            "vt_symbol": "600519.SSE",
            "symbol": "600519",
            "name": "贵州茅台",
            "change_pct": 10.0,
        }
        mock_limit.return_value = (
            {
                "vt_symbol": "600519.SSE",
                "limit_times": 2,
                "first_time": "0931",
                "last_time": "1455",
                "fd_amount": 120000000.0,
                "open_times": 0,
            },
            "20240618",
        )
        mock_resolve_boards.return_value = 2.0
        mock_limit_map.return_value = {}
        mock_leaders.return_value = ("白酒", "dragon_1", 1, [])
        entry = MagicMock()
        entry.to_dict.return_value = {
            "recommended_label": "打板",
            "emotion_stage_label": "启动",
            "allow_new_positions": True,
            "scores": [{"label": "打板", "score": 72, "reasons": ["连板 2"]}],
            "warnings": [],
            "allowed_mode_labels": ["打板", "半路"],
        }
        mock_entry.return_value = entry
        _mock_reg.return_value = None

        profile = build_short_term_profile("600519.SSE")
        self.assertEqual(profile.vt_symbol, "600519.SSE")
        self.assertEqual(profile.limit_times, 2.0)
        self.assertEqual(profile.leader_tier, "dragon_1")
        self.assertEqual(profile.trade_date, "20240618")
        self.assertEqual(profile.entry_mode.get("recommended_label"), "打板")


if __name__ == "__main__":
    unittest.main()
