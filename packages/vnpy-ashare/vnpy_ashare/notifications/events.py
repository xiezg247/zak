"""出站通知事件 ID 与默认订阅。"""

from __future__ import annotations

NOTIFY_EVENT_SCREENER_INTRADAY_DONE = "screener_intraday_done"
NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE = "screener_post_close_done"
NOTIFY_EVENT_SCHEDULER_JOB_FAILED = "scheduler_job_failed"
NOTIFY_EVENT_MANUAL_TEST = "manual_test"

DEFAULT_EVENT_SUBSCRIPTIONS: dict[str, bool] = {
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE: True,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE: False,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED: True,
}
