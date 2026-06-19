"""limit_list 单票历史与 top_list 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.integrations.tushare.limit_list_fallback import fetch_symbol_limit_history
from vnpy_ashare.integrations.tushare.top_list import fetch_top_list_history
from vnpy_ashare.services.stock.short_term import _build_limit_history, build_short_term_profile


class LimitHistoryTests(unittest.TestCase):
    @patch("vnpy_ashare.integrations.tushare.limit_list_fallback.fetch_limit_list_d")
    @patch("vnpy_ashare.integrations.tushare.limit_list_fallback.iter_trade_date_strs")
    def test_fetch_symbol_limit_history(self, mock_dates, mock_fetch) -> None:
        mock_dates.return_value = ["20240618", "20240617"]

        def _side_effect(*, trade_date: str, limit_type: str | None = None):
            if trade_date == "20240618":
                return (
                    [
                        {
                            "ts_code": "600519.SH",
                            "vt_symbol": "600519.SSE",
                            "limit_times": 2,
                            "open_times": 0,
                        }
                    ],
                    trade_date,
                )
            return ([], trade_date)

        mock_fetch.side_effect = _side_effect
        rows = fetch_symbol_limit_history(ts_code="600519.SH", vt_symbol="600519.SSE", max_days=2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trade_date"], "20240618")

    @patch("vnpy_ashare.services.stock.short_term.fetch_symbol_limit_history")
    def test_build_limit_history_stats(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {"trade_date": "20240618", "limit_times": 2, "open_times": 0, "first_time": "0930"},
            {"trade_date": "20240617", "limit_times": 1, "open_times": 2, "first_time": "1015"},
        ]
        history, stats = _build_limit_history("600519.SH", "600519.SSE")
        self.assertEqual(len(history), 2)
        self.assertEqual(stats.limit_up_days, 2)
        self.assertEqual(stats.open_board_days, 1)
        self.assertEqual(stats.solid_seal_days, 1)


class TopListHistoryTests(unittest.TestCase):
    @patch("vnpy_ashare.integrations.tushare.top_list.fetch_top_list_for_date")
    @patch("vnpy_ashare.integrations.tushare.top_list.iter_trade_date_strs")
    def test_fetch_top_list_history(self, mock_dates, mock_fetch) -> None:
        mock_dates.return_value = ["20240618", "20240617"]
        mock_fetch.side_effect = lambda *, trade_date, ts_code: (
            [{"trade_date": trade_date, "reason": "测试", "net_amount": 1.0}] if trade_date == "20240618" else []
        )
        rows = fetch_top_list_history("600519.SH", max_days=2, limit=3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trade_date"], "20240618")


class ShortTermProfileExtendedTests(unittest.TestCase):
    @patch("vnpy_ashare.services.stock.short_term._build_top_list")
    @patch("vnpy_ashare.services.stock.short_term._build_limit_history")
    @patch("vnpy_ashare.services.stock.short_term.assess_regulatory_deviation_for_vt_symbol")
    @patch("vnpy_ashare.services.stock.short_term.load_emotion_cycle_snapshot")
    @patch("vnpy_ashare.services.stock.short_term.evaluate_entry_mode")
    @patch("vnpy_ashare.services.stock.short_term._resolve_sector_leaders")
    @patch("vnpy_ashare.services.stock.short_term.attach_seal_reopen_fields")
    @patch("vnpy_ashare.services.stock.short_term.seal_reopen_from_row")
    @patch("vnpy_ashare.services.stock.short_term.seal_strength_from_row")
    @patch("vnpy_ashare.services.stock.short_term.get_cached_limit_times_map")
    @patch("vnpy_ashare.services.stock.short_term.resolve_limit_times")
    @patch("vnpy_ashare.services.stock.short_term._find_limit_today")
    @patch("vnpy_ashare.services.stock.short_term._merge_quote_row")
    def test_build_short_term_profile_extended(
        self,
        mock_merge: MagicMock,
        mock_limit: MagicMock,
        mock_resolve_boards: MagicMock,
        _mock_limit_map: MagicMock,
        mock_strength: MagicMock,
        mock_reopen: MagicMock,
        _mock_seal: MagicMock,
        mock_leaders: MagicMock,
        mock_entry: MagicMock,
        _mock_cycle: MagicMock,
        _mock_reg: MagicMock,
        mock_limit_hist: MagicMock,
        mock_top: MagicMock,
    ) -> None:
        from vnpy_ashare.domain.stock.short_term import LimitHistoryRow, LimitStats, TopInstRow, TopListRow

        mock_merge.return_value = {"vt_symbol": "600519.SSE", "symbol": "600519", "name": "贵州茅台"}
        mock_limit.return_value = ({"limit_times": 2, "open_times": 0}, "20240618")
        mock_resolve_boards.return_value = 2.0
        mock_strength.return_value = 0.82
        mock_reopen.return_value = ("solid", "首封未开", 1.0, 0)
        mock_leaders.return_value = ("白酒", "dragon_1", 1, [])
        entry = MagicMock()
        entry.to_dict.return_value = {"recommended_label": "打板", "scores": []}
        mock_entry.return_value = entry
        mock_limit_hist.return_value = (
            [LimitHistoryRow(trade_date="20240618", limit_times=2.0, open_times=0)],
            LimitStats(limit_up_days=1, open_board_days=0, solid_seal_days=1),
        )
        mock_top.return_value = (
            [TopListRow(trade_date="20240610", reason="测试")],
            [TopInstRow(exalter="机构专用", buy=1e7, net_buy=1e7)],
            [],
            "20240610",
        )
        _mock_reg.return_value = None

        profile = build_short_term_profile("600519.SSE")
        self.assertEqual(profile.seal_strength_label, "强")
        self.assertEqual(profile.limit_stats.limit_up_days if profile.limit_stats else 0, 1)
        self.assertEqual(len(profile.top_list), 1)
        self.assertEqual(len(profile.top_inst_buy), 1)


if __name__ == "__main__":
    unittest.main()
