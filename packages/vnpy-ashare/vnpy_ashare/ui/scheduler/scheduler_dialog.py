"""定时任务管理对话框（兼容保留，主入口已迁至导航页）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.scheduler import TaskSchedulerManager
from vnpy_ashare.ui.scheduler.scheduler_jobs_widget import SchedulerJobsWidget
from vnpy_common.ui.theme import theme_manager


class SchedulerDialog(QtWidgets.QDialog):
    """定时任务列表：启停、立即执行、调度参数。"""

    def __init__(
        self,
        scheduler: TaskSchedulerManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scheduler = scheduler
        self.setWindowTitle("定时任务")
        self.setMinimumSize(1020, 480)
        self.resize(1080, 520)
        theme_manager().bind_stylesheet(self)

        hint = QtWidgets.QLabel("生产环境建议独立运行 scripts/quote_collector.py；此处「行情采集」适合本机调试。")
        hint.setWordWrap(True)

        self._jobs_widget = SchedulerJobsWidget(scheduler, self)

        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(self.accept)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self._jobs_widget, stretch=1)
        layout.addLayout(button_row)
