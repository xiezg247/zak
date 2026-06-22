"""板块资金 ↔ 雷达/龙头跳转。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.ui.quotes.radar.controller import RadarController


class SectorFlowRadarLinkTests(unittest.TestCase):
    def test_open_external_card_focuses_and_refreshes(self) -> None:
        board = mock.Mock()
        board.focus_card.return_value = True
        board.card.return_value = mock.Mock()
        page = mock.Mock()
        controller = RadarController.__new__(RadarController)
        controller._board = board
        controller._card_variants = {"leader_pick": "mainline", "sector_theme": "breadth"}
        controller._sector_variant = "breadth"
        controller.refresh_card = mock.Mock()

        ok = controller.open_external_card("leader_pick", refresh=True)

        self.assertTrue(ok)
        board.focus_card.assert_called_once_with("leader_pick")
        controller.refresh_card.assert_called_once_with("leader_pick")

    def test_open_external_card_applies_variant(self) -> None:
        board = mock.Mock()
        board.focus_card.return_value = True
        card_widget = mock.Mock()
        board.card.return_value = card_widget
        page = mock.Mock()
        controller = RadarController.__new__(RadarController)
        controller._board = board
        controller._card_variants = {"sector_theme": "breadth"}
        controller._sector_variant = "breadth"
        controller.refresh_card = mock.Mock()

        controller.open_external_card("sector_theme", variant="leaders_tiered", refresh=False)

        self.assertEqual(controller._card_variants["sector_theme"], "leaders_tiered")
        self.assertEqual(controller._sector_variant, "leaders_tiered")
        card_widget.set_variant_key.assert_called_once_with("leaders_tiered")
        controller.refresh_card.assert_not_called()


if __name__ == "__main__":
    unittest.main()
