"""市场页榜单侧栏交互测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.quotes.rank_catalog import DEFAULT_RANK_ID
from vnpy_ashare.ui.quotes.features.market_rank import MarketRankFeature
from vnpy_ashare.ui.quotes.features.market_rank_sidebar import KIND_RANK, RANK_ID_ROLE, RANK_ROW_KIND_ROLE


def _ensure_qapp() -> None:
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])


class _FakeRankList(QtWidgets.QListWidget):
    def __init__(self) -> None:
        super().__init__()
        for rank_id, title in (
            (DEFAULT_RANK_ID, "涨幅榜"),
            ("net_mf_in", "主力净流入"),
        ):
            item = QtWidgets.QListWidgetItem(title)
            item.setData(RANK_ID_ROLE, rank_id)
            item.setData(RANK_ROW_KIND_ROLE, KIND_RANK)
            self.addItem(item)


class MarketRankToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def _build_feature(self, *, rank_id: str = "net_mf_in") -> tuple[MarketRankFeature, SimpleNamespace]:
        page = SimpleNamespace(
            config=SimpleNamespace(show_rank_sidebar=True, default_rank_id=DEFAULT_RANK_ID),
            _market_sort_column="",
            _market_sort_ascending=False,
            _market_page=0,
            _market_page_cache={},
            _market_catalog_loaded=True,
            _market_board_base=None,
            _market_board_base_key=None,
            _market_filter_keyword="",
            _market_loading_more=False,
            _market_last_load_more_at=0.0,
            rank_list=_FakeRankList(),
            load_stock_list=MagicMock(),
        )
        feature = MarketRankFeature(page)  # type: ignore[arg-type]
        page._market_rank_id = rank_id
        return feature, page

    def test_click_same_rank_resets_to_default(self) -> None:
        feature, page = self._build_feature(rank_id="net_mf_in")
        item = page.rank_list.item(1)
        self.assertIsNotNone(item)
        feature.on_rank_item_clicked(item)
        self.assertEqual(page._market_rank_id, DEFAULT_RANK_ID)
        page.load_stock_list.assert_called_once()

    def test_click_default_rank_twice_is_noop(self) -> None:
        feature, page = self._build_feature(rank_id=DEFAULT_RANK_ID)
        item = page.rank_list.item(0)
        self.assertIsNotNone(item)
        feature.on_rank_item_clicked(item)
        page.load_stock_list.assert_not_called()


if __name__ == "__main__":
    unittest.main()
