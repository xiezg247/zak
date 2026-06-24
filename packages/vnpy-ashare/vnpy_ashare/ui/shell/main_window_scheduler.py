"""主窗口 Scheduler 延迟启动与通知。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore

from vnpy_ashare.app.engine import APP_NAME, AshareEngine
from vnpy_ashare.app.events import EVENT_ORB_ATTENTION, OrbAttentionRequest
from vnpy_ashare.services.industry_sector import get_cached_industry_map
from vnpy_common.startup_profile import profiler

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.main_window import AshareMainWindow


def schedule_deferred_shell_extras(win: AshareMainWindow) -> None:
    """首屏渲染后再初始化悬浮 AI 等非关键壳层组件。"""
    if win._shell_extras_scheduled:
        return
    win._shell_extras_scheduled = True
    QtCore.QTimer.singleShot(0, lambda: _load_deferred_shell_extras(win))


def _load_deferred_shell_extras(win: AshareMainWindow) -> None:
    with profiler.phase("main_window.floating_ai"):
        shell = win.centralWidget()
        if shell is not None and win._init_floating_ai(shell):
            assert win._floating_controller is not None
            win._floating_controller.bind_content_anchor(win.stack)
    with profiler.phase("main_window.info_feed_badge"):
        refresh_info_feed_badge(win)


def schedule_deferred_scheduler_start(win: AshareMainWindow) -> None:
    """冷启动：首屏渲染完成后再启动 APScheduler，避免与窗口首帧争抢。"""
    if win._scheduler_deferred_scheduled:
        return
    win._scheduler_deferred_scheduled = True
    QtCore.QTimer.singleShot(4000, lambda: deferred_scheduler_start(win))


def deferred_scheduler_start(win: AshareMainWindow) -> None:
    engine = win.main_engine.get_engine(APP_NAME)
    if isinstance(engine, AshareEngine):
        engine.scheduler.ensure_started()
        bootstrap_stock_industry_if_needed(engine.scheduler)


def bootstrap_stock_industry_if_needed(scheduler) -> None:
    """行业映射缓存为空时，调度器启动后补跑一次同步任务。"""
    if get_cached_industry_map() is not None:
        return
    if not scheduler.get_job_config("sync_stock_industry").enabled:
        return
    scheduler.run_now("sync_stock_industry")


def refresh_info_feed_badge(win: AshareMainWindow) -> None:
    win.sidebar.set_badge_count("info_feed", 0)


def bind_scheduler_notifications(win: AshareMainWindow) -> None:
    if win._scheduler_listener_connected:
        return
    engine = win.main_engine.get_engine(APP_NAME)
    if not isinstance(engine, AshareEngine):
        return
    engine.scheduler.add_listener(win._on_scheduler_job_event)
    win._scheduler_listener_connected = True


def on_scheduler_job_event(win: AshareMainWindow, job_id: str) -> None:
    win._signal_scheduler_job.emit(job_id)


def handle_scheduler_job(win: AshareMainWindow, job_id: str) -> None:
    if job_id == "sync_bilibili_feed":
        refresh_info_feed_badge(win)
        widget = win._page_widgets.get("info_feed")
        if widget is not None and hasattr(widget, "activate"):
            widget.activate()
        return
    if job_id not in ("screen_intraday", "screen_post_close"):
        return
    engine = win.main_engine.get_engine(APP_NAME)
    if not isinstance(engine, AshareEngine):
        return
    status = engine.scheduler.get_status(job_id)
    if status is None or status.last_success is not True:
        return
    message = status.last_message or "多因子配方已完成"
    if message and "跳过" in message:
        return
    widget = win._page_widgets.get("screener")
    if widget is not None and hasattr(widget, "on_scheduled_run_complete"):
        widget.on_scheduled_run_complete(job_id, message)
    if win._current_key != "screener":
        win.event_engine.put(
            Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="auto_screener")),
        )
