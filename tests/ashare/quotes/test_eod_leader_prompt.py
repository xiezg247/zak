"""雷达盘后龙头解读 prompt 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.domain.radar.card import RadarCardData, RadarRow
from vnpy_ashare.quotes.radar.radar_loaders import build_eod_leader_prompt


def _row(vt_symbol: str = "600519.SSE", *, leader_tier: str = "dragon_1") -> RadarRow:
    return RadarRow(
        vt_symbol=vt_symbol,
        symbol="600519",
        name="贵州茅台",
        price=1800.0,
        change_pct=10.0,
        metric_label="连板",
        metric_value="3",
        sub_label="板块",
        sub_value="白酒",
        leader_tier=leader_tier,
    )


class BuildEodLeaderPromptTest(unittest.TestCase):
    @patch("vnpy_ashare.quotes.market.emotion_cycle.load_emotion_cycle_snapshot", return_value=None)
    def test_includes_leader_card_rows(self, _load_cycle) -> None:
        payload = {
            "leader_pick": RadarCardData(
                card_id="leader_pick",
                title="选股·龙头",
                subtitle="",
                rows=(_row(),),
                empty_message="暂无",
                updated_at="2026-06-18",
            ),
        }
        prompt = build_eod_leader_prompt(payload)
        self.assertIn("今日龙头结构", prompt)
        self.assertIn("贵州茅台", prompt)
        self.assertIn("dragon_1", prompt)

    @patch("vnpy_ashare.quotes.market.emotion_cycle.load_emotion_cycle_snapshot", return_value=None)
    def test_empty_when_no_focus_cards(self, _load_cycle) -> None:
        self.assertEqual(build_eod_leader_prompt({}), "")


if __name__ == "__main__":
    unittest.main()
