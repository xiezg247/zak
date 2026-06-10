"""TaskRunOutputPanel 单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel


class TaskRunOutputPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_begin_task_and_complete(self) -> None:
        panel = TaskRunOutputPanel(log_placeholder="暂无执行日志")
        panel.begin_task("补全 002230.SZSE 日K")
        panel.complete_task(summary="新增 7 根", detail="数据源 Tushare")

        self.assertIn("新增 7 根", panel._summary_label.text())
        log_text = panel._log_view.toPlainText()
        self.assertIn("[开始] 补全 002230.SZSE 日K", log_text)
        self.assertIn("[完成]", log_text)
        self.assertIn("数据源 Tushare", log_text)


if __name__ == "__main__":
    unittest.main()
