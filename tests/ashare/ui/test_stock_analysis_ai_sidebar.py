"""个股分析 AI 侧栏全屏跳转测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.features.stock_analysis.ai_sidebar import StockAnalysisAiSidebar
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost


class StockAnalysisAiSidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_open_full_ai_page_hides_dialog_and_switches_assistant(self) -> None:
        main = QtWidgets.QWidget()
        main._open_ai_page = MagicMock()
        main.unregister_floating_overlay = MagicMock()

        dialog = QtWidgets.QDialog(main)
        dialog.show()

        host = StockAnalysisHost.from_main_engine(MagicMock(), source_page="自选")
        sidebar = StockAnalysisAiSidebar(host, dialog)
        sidebar.attach_splitter(QtWidgets.QSplitter())

        engine = MagicMock()
        sidebar._engine = engine
        sidebar._find_main_window = lambda: main

        sidebar._open_full_ai_page()

        engine.open_session_for_ask.assert_called_once_with(
            surface="assistant",
            session_policy="resume",
            scene="个股分析·自选",
        )
        main.unregister_floating_overlay.assert_called_once_with(dialog)
        self.assertFalse(dialog.isVisible())
        main._open_ai_page.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
