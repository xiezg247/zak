"""Scheduler 选主与用户级任务。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from vnpy_ashare.domain.core.env import env_bool
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_common.auth.context import clear_current_user, set_current_user

logger = logging.getLogger(__name__)

USER_SCOPED_JOB_IDS: frozenset[str] = frozenset(
    {
        "sync_bilibili_feed",
        "screen_intraday",
        "screen_post_close",
        "warm_watchlist_strategy_cache",
        "sync_watchlist_financials",
        "sync_disclosure_calendar",
        "fill_focus_pool_minute",
        "batch_fill_stale",
    }
)


def should_run_scheduler() -> bool:
    """仅 ZAK_RUN_SCHEDULER=true 的机器启动 APScheduler。"""
    return bool(env_bool("ZAK_RUN_SCHEDULER"))


def is_user_scoped_job(job_id: str) -> bool:
    return job_id in USER_SCOPED_JOB_IDS


def run_job_for_active_users(
    job_id: str,
    runner: Callable[[], JobResult],
) -> JobResult:
    """Leader 遍历活跃用户，在各自 user context 下执行任务。"""
    from vnpy_ashare.storage.auth.users import list_active_users

    users = list_active_users()
    if not users:
        return JobResult(success=True, skipped=True, message="无活跃用户，已跳过")

    messages: list[str] = []
    success = True
    skipped_all = True
    for user in users:
        set_current_user(user.id)
        try:
            result = runner()
        finally:
            clear_current_user()
        label = user.username or user.id[:8]
        messages.append(f"{label}: {result.message}")
        if not result.skipped:
            skipped_all = False
        if not result.success and not result.skipped:
            success = False

    summary = "；".join(messages)
    if skipped_all:
        return JobResult(success=True, skipped=True, message=summary)
    return JobResult(success=success, message=summary)
