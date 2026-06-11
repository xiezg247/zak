"""策略选股运行输出面板（复用 TaskRunOutputPanel）。"""

from __future__ import annotations

from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel


class ScreenerRunOutputPanel(TaskRunOutputPanel):
    """左栏下半区：最近一次运行摘要 + 过程日志。"""

    def __init__(
        self,
        parent=None,
        *,
        log_placeholder: str = "暂无日志",
    ) -> None:
        super().__init__(
            parent,
            title="运行输出",
            log_placeholder=log_placeholder,
            object_name="ScreenerRunOutputPanel",
            section_label_object_name="ScreenerSectionLabel",
            summary_object_name="ScreenerRunSummary",
            log_view_object_name="ScreenerRunLogView",
        )
