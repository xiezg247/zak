"""策略选股运行输出面板单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.screener_run_output_panel import ScreenerRunOutputPanel


class ScreenerRunOutputPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_idle_hides_summary_and_shows_placeholder_only(self) -> None:
        panel = ScreenerRunOutputPanel()
        self.assertEqual(panel._summary_label.text(), "")
        self.assertEqual(panel._log_view.placeholderText(), "暂无日志")

    def test_begin_and_complete_run_updates_summary_and_log(self) -> None:
        panel = ScreenerRunOutputPanel()
        panel.begin_run(label="涨幅榜", top_n=20)
        panel.complete_run(summary="命中 3 条", detail="数据源 redis")

        self.assertIn("命中 3 条", panel._summary_label.text())
        log_text = panel._log_view.toPlainText()
        self.assertIn("[开始]", log_text)
        self.assertIn("涨幅榜", log_text)
        self.assertIn("[完成]", log_text)
        self.assertNotIn("命中 3 条", log_text)
        self.assertIn("数据源 redis", log_text)

    def test_fail_run_sets_error_summary(self) -> None:
        panel = ScreenerRunOutputPanel()
        panel.fail_run("Redis 无快照")

        self.assertEqual(panel._summary_label.text(), "运行失败")
        self.assertIn("[错误] Redis 无快照", panel._log_view.toPlainText())

    def test_load_history_does_not_duplicate_summary_in_log(self) -> None:
        panel = ScreenerRunOutputPanel()
        panel.load_history(summary="命中 5 条 · 扫描 100 只")

        self.assertIn("命中 5 条", panel._summary_label.text())
        self.assertEqual(panel._log_view.toPlainText(), "[历史] 已载入")


if __name__ == "__main__":
    unittest.main()
