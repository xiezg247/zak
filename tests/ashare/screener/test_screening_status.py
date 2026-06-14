"""选股数据状态与洞察纯函数测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.screener.data.screening_status import (
    format_diff_insight,
    format_sector_insight,
    preset_uses_live_quotes,
    recipe_uses_live_quotes,
    resolve_run_trigger_kind,
)
from vnpy_ashare.screener.preset.presets import SCREENER_CHANGE_TOP, SCREENER_LOW_PE
from vnpy_ashare.screener.recipe.recipe import BUILTIN_RECIPES, RECIPE_INTRADAY_MULTI, RECIPE_POST_CLOSE_MULTI


class ScreeningStatusTests(unittest.TestCase):
    def test_preset_uses_live_quotes(self) -> None:
        self.assertTrue(preset_uses_live_quotes(SCREENER_CHANGE_TOP))
        self.assertFalse(preset_uses_live_quotes(SCREENER_LOW_PE))

    def test_recipe_uses_live_quotes(self) -> None:
        self.assertTrue(recipe_uses_live_quotes(BUILTIN_RECIPES[RECIPE_INTRADAY_MULTI]))
        self.assertFalse(recipe_uses_live_quotes(BUILTIN_RECIPES[RECIPE_POST_CLOSE_MULTI]))

    def test_resolve_run_trigger_kind_from_scheduled(self) -> None:
        self.assertEqual(resolve_run_trigger_kind({"trigger": "scheduled_intraday"}), "intraday")
        self.assertEqual(resolve_run_trigger_kind({"trigger": "scheduled_post_close"}), "post_close")

    def test_resolve_run_trigger_kind_from_recipe_id(self) -> None:
        kind = resolve_run_trigger_kind({"trigger": "manual", "recipe_id": RECIPE_INTRADAY_MULTI})
        self.assertEqual(kind, "intraday")

    def test_resolve_run_trigger_kind_from_explicit(self) -> None:
        self.assertEqual(resolve_run_trigger_kind({"trigger_kind": "post_close"}), "post_close")

    def test_format_diff_insight(self) -> None:
        text = format_diff_insight({"run_diff": {"new_count": 3, "stay_count": 5, "drop_count": 2}})
        self.assertIn("新增 3", text)
        self.assertIn("保留 5", text)
        self.assertIn("剔除 2", text)

    @patch("vnpy_ashare.screener.data.screening_status.attach_industry")
    @patch("vnpy_ashare.screener.data.screening_status.compute_sector_distribution")
    def test_format_sector_insight(self, mock_dist, mock_attach) -> None:
        mock_attach.return_value = [{"industry": "半导体", "change_pct": 2.5}]
        mock_dist.return_value = [{"industry": "半导体", "count": 2, "avg_change_pct": 2.5}]
        text = format_sector_insight([{"vt_symbol": "600000.SSE"}])
        self.assertIn("行业分布", text)
        self.assertIn("半导体", text)


if __name__ == "__main__":
    unittest.main()
