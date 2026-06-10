"""看盘页运行输出面板写入（本地 / 自选等）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes_page import QuotesPage
    from vnpy_ashare.ui.task_run_output_panel import TaskRunOutputPanel


def run_output_panel(page: QuotesPage) -> TaskRunOutputPanel | None:
    if not page.config.show_run_output_panel:
        return None
    panel = getattr(page, "run_output_panel", None)
    return panel


def append_run_log(page: QuotesPage, message: str) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        panel.append_log(message)


def begin_run_log(page: QuotesPage, title: str) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        panel.begin_task(title)


def complete_run_log(page: QuotesPage, summary: str, *, detail: str | None = None) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        panel.complete_task(summary=summary, detail=detail)


def fail_run_log(page: QuotesPage, message: str) -> None:
    panel = run_output_panel(page)
    if panel is not None:
        panel.fail_task(message)
