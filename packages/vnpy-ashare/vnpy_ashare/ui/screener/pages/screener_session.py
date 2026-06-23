"""ScreenerPageWidget 激活 / 停用生命周期。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context.screener import sync_screener_page_context


def activate_screener_page(page: Any) -> None:
    page._active = True
    page._reload_preset_combo()
    page.run_sidebar.refresh()
    page._status_controller.activate()
    sync_screener_page_context(page.main_engine)


def deactivate_screener_page(page: Any) -> None:
    page._active = False
    page._status_controller.deactivate()
    page._run_controller.cancel_screening()
    if page._download_worker is not None:
        page._download_worker.request_cancel()
    page._task_guard.end()
    page._run_controller.release_workers(timeout_ms=0)
    worker = page._download_worker
    page._download_worker = None
    page._release_worker(worker, timeout_ms=0)
    if page._batch_backtest_flow is not None:
        page._batch_backtest_flow.release_worker(page._retired_workers, timeout_ms=0)
