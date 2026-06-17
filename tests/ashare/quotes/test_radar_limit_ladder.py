"""连板梯队分组与排序测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.radar.radar_limit_ladder import (
    build_limit_ladder_candidates,
    count_ladder_buckets,
    ladder_bucket_label,
    resolve_limit_times,
    select_by_height,
    select_by_sector,
)


def _row(symbol: str, *, boards: int = 1, industry: str = "半导体", amount: float = 1e8) -> dict:
    return {
        "vt_symbol": f"{symbol}.SSE",
        "symbol": symbol,
        "name": symbol,
        "industry": industry,
        "limit_times": boards,
        "change_pct": 10.0,
        "amount": amount,
    }


class LimitLadderTest(unittest.TestCase):
    def test_ladder_bucket_label(self) -> None:
        self.assertEqual(ladder_bucket_label(5), "5板+")
        self.assertEqual(ladder_bucket_label(4), "4板")
        self.assertEqual(ladder_bucket_label(1), "首板")

    def test_resolve_limit_times_from_row(self) -> None:
        self.assertEqual(resolve_limit_times(_row("A", boards=3), limit_times_map={}), 3)

    def test_resolve_limit_times_from_map(self) -> None:
        row = {"vt_symbol": "600000.SSE", "change_pct": 10.0, "amount": 1e8}
        boards = resolve_limit_times(row, limit_times_map={"600000.SH": 4})
        self.assertEqual(boards, 4)

    @patch("vnpy_ashare.quotes.radar.radar_limit_ladder.apply_screening_filters", side_effect=lambda rows: rows)
    def test_build_limit_ladder_candidates_filters_non_limit(self, _filters) -> None:
        rows = [_row("A", boards=3), _row("B", boards=0, amount=1e7)]
        rows[1]["change_pct"] = 3.0
        candidates = build_limit_ladder_candidates(rows, limit_times_map={})
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["symbol"], "A")

    def test_count_ladder_buckets(self) -> None:
        rows = [_row("A", boards=5), _row("B", boards=2), _row("C", boards=1)]
        counts = count_ladder_buckets(rows)
        self.assertEqual(counts["5板+"], 1)
        self.assertEqual(counts["2板"], 1)
        self.assertEqual(counts["首板"], 1)

    def test_select_by_height_orders_boards_first(self) -> None:
        rows = [_row("low", boards=2), _row("high", boards=5, amount=2e8)]
        picked = select_by_height(rows, top_n=1)
        self.assertEqual(picked[0]["symbol"], "high")

    def test_select_by_sector_picks_one_per_industry(self) -> None:
        rows = [
            _row("A", boards=3, industry="半导体"),
            _row("B", boards=2, industry="半导体"),
            _row("C", boards=4, industry="银行"),
        ]
        picked = select_by_sector(rows, top_n=10)
        symbols = {row["symbol"] for row in picked}
        self.assertEqual(symbols, {"A", "C"})

    @patch("vnpy_ashare.quotes.radar.radar_limit_ladder.get_cached_limit_times_map", return_value={})
    @patch("vnpy_ashare.quotes.radar.radar_limit_ladder.attach_industry", side_effect=lambda rows: rows)
    @patch("vnpy_ashare.quotes.radar.radar_limit_ladder.load_screening_quote_snapshot")
    def test_load_limit_ladder_empty_when_no_limit_up(self, mock_snapshot, _industry, _limit_map) -> None:
        from types import SimpleNamespace

        from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
        from vnpy_ashare.quotes.radar.radar_limit_ladder import load_limit_ladder

        mock_snapshot.return_value = SimpleNamespace(rows=[_row("A", boards=0)], total=100)
        mock_snapshot.return_value.rows[0]["change_pct"] = 1.0
        spec = RADAR_CARD_BY_ID["discovery_limit_ladder"]
        with patch(
            "vnpy_ashare.quotes.radar.radar_limit_ladder.build_limit_ladder_candidates",
            return_value=[],
        ):
            data = load_limit_ladder(spec)
        self.assertEqual(data.rows, ())
        self.assertIn("暂无涨停梯队", data.empty_message)
