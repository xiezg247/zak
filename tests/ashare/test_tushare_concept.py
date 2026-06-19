"""概念接口单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.concept import fetch_stock_concepts


class FetchStockConceptsTests(unittest.TestCase):
    @patch("vnpy_ashare.integrations.tushare.concept.fetch_ths_concept_index_map")
    @patch("vnpy_ashare.integrations.tushare.concept.get_tushare_pro")
    def test_prefers_ths_member(self, mock_get_pro, mock_index_map) -> None:
        pro = MagicMock()
        mock_get_pro.return_value = pro
        mock_index_map.return_value = {"885800.TI": "消费电子概念"}
        pro.ths_member.return_value = pd.DataFrame(
            [{"ts_code": "885800.TI", "con_code": "600519.SH"}]
        )

        rows = fetch_stock_concepts("600519.SH")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["concept_name"], "消费电子概念")
        self.assertEqual(rows[0]["concept_id"], "885800.TI")
        pro.concept_detail.assert_not_called()

    @patch("vnpy_ashare.integrations.tushare.concept.fetch_ths_concept_index_map")
    @patch("vnpy_ashare.integrations.tushare.concept.get_tushare_pro")
    def test_falls_back_to_concept_detail(self, mock_get_pro, mock_index_map) -> None:
        pro = MagicMock()
        mock_get_pro.return_value = pro
        mock_index_map.return_value = {}
        pro.ths_member.return_value = pd.DataFrame()
        pro.concept_detail.return_value = pd.DataFrame(
            [{"id": "TS2", "concept_name": "5G", "ts_code": "600519.SH", "name": "贵州茅台"}]
        )

        rows = fetch_stock_concepts("600519.SH")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["concept_name"], "5G")
        pro.concept_detail.assert_called_once()

    @patch("vnpy_ashare.integrations.tushare.concept.get_tushare_pro")
    def test_raises_when_not_configured(self, mock_get_pro) -> None:
        mock_get_pro.side_effect = TushareNotConfiguredError("missing token")
        with self.assertRaises(TushareNotConfiguredError):
            fetch_stock_concepts("600519.SH")


if __name__ == "__main__":
    unittest.main()
