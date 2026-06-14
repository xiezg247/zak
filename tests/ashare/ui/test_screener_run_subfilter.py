"""自动选股侧栏盘中/盘后过滤测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.screener.recipe.recipe import RECIPE_INTRADAY_MULTI, RECIPE_POST_CLOSE_MULTI
from vnpy_ashare.ui.screener.widgets.screener_run_sidebar import ScreenerRunSidebar


def _ensure_qapp() -> None:
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])


class ScreenerRunSubfilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def _list_widget(self) -> SimpleNamespace:
        sidebar = ScreenerRunSidebar(mode="auto", main_engine=MagicMock(), parent=None)
        return sidebar._list  # type: ignore[attr-defined]

    def test_manual_intraday_recipe_matches_intraday_tab(self) -> None:
        widget = self._list_widget()
        widget._filter = "intraday"
        record = SimpleNamespace(config={"trigger": "manual", "recipe_id": RECIPE_INTRADAY_MULTI})
        self.assertTrue(widget._matches_subfilter(record))

    def test_manual_post_close_recipe_matches_post_close_tab(self) -> None:
        widget = self._list_widget()
        widget._filter = "post_close"
        record = SimpleNamespace(config={"trigger": "manual", "recipe_id": RECIPE_POST_CLOSE_MULTI})
        self.assertTrue(widget._matches_subfilter(record))

    def test_intraday_tab_excludes_post_close_recipe(self) -> None:
        widget = self._list_widget()
        widget._filter = "intraday"
        record = SimpleNamespace(config={"trigger": "manual", "recipe_id": RECIPE_POST_CLOSE_MULTI})
        self.assertFalse(widget._matches_subfilter(record))


if __name__ == "__main__":
    unittest.main()
