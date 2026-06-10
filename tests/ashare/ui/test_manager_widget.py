"""数据管理页 UI 测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.app_db import add_watchlist_item, build_symbol_name_map, init_app_db, save_universe_rows
from vnpy_ashare.ui.shell.manager_widget import _DOWNLOAD_HINT, _TREE_LABELS, ManagerWidget


class ManagerWidgetUiTests(unittest.TestCase):
    def test_download_hint_documents_other_entrypoints(self) -> None:
        self.assertIn("自选", _DOWNLOAD_HINT)
        self.assertIn("本地", _DOWNLOAD_HINT)
        self.assertIn("同步 A 股列表", _DOWNLOAD_HINT)

    def test_activate_refreshes_tree(self) -> None:
        widget = ManagerWidget.__new__(ManagerWidget)
        widget.refresh_tree = MagicMock()
        ManagerWidget.activate(widget)
        widget.refresh_tree.assert_called_once()

    def test_tree_has_security_name_column(self) -> None:
        self.assertIn("证券名称", _TREE_LABELS)
        self.assertEqual(_TREE_LABELS.index("证券名称"), 3)


class SymbolNameMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.app_db.get_app_db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_build_symbol_name_map_prefers_universe(self) -> None:
        save_universe_rows([("600519", Exchange.SSE, "贵州茅台")])
        add_watchlist_item("600519", Exchange.SSE, "自选名")
        mapping = build_symbol_name_map()
        self.assertEqual(mapping[("600519", Exchange.SSE)], "贵州茅台")

    def test_build_symbol_name_map_falls_back_to_watchlist(self) -> None:
        add_watchlist_item("000001", Exchange.SZSE, "平安银行")
        mapping = build_symbol_name_map()
        self.assertEqual(mapping[("000001", Exchange.SZSE)], "平安银行")


if __name__ == "__main__":
    unittest.main()
