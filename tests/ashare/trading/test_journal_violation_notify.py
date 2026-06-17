"""流水违规通知测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy_ashare.notifications.events import NOTIFY_EVENT_JOURNAL_VIOLATION
from vnpy_ashare.notifications.formatters import format_notify_text
from vnpy_ashare.trading.journal.violation_notify import format_violation_tags, publish_journal_violation


def test_format_violation_tags() -> None:
    assert format_violation_tags(("off_plan", "recession_buy")) == "计划外 · 退潮买入"


def test_format_notify_journal_violation() -> None:
    text = format_notify_text(
        NOTIFY_EVENT_JOURNAL_VIOLATION,
        {
            "symbol": "600000",
            "exchange": "SSE",
            "side": "buy",
            "violation_tags": "计划外",
            "reason": "登记买入",
        },
    )
    assert "交易纪律" in text
    assert "600000" in text
    assert "计划外" in text


def test_publish_journal_violation_skips_empty_tags() -> None:
    engine = MagicMock()
    publish_journal_violation(engine, symbol="600000", exchange="SSE", side="buy", violation_tags=())
    engine.notification_service.notify.assert_not_called()


def test_publish_journal_violation_notifies() -> None:
    engine = MagicMock()
    publish_journal_violation(
        engine,
        symbol="600000",
        exchange="SSE",
        side="buy",
        violation_tags=("off_plan",),
        reason="登记买入",
    )
    engine.notification_service.notify.assert_called_once()
    args, kwargs = engine.notification_service.notify.call_args
    assert args[0] == NOTIFY_EVENT_JOURNAL_VIOLATION
