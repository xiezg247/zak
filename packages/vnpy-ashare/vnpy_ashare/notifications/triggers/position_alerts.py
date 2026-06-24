"""持仓异动 → 通知扫描。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.notifications.core.events import NOTIFY_EVENT_POSITION_ALERT
from vnpy_ashare.notifications.core.position_alert_scan import PositionAlertScanInput
from vnpy_ashare.quotes.misc.position_anomaly import format_anomaly_tags, is_position_anomaly, position_anomaly_reasons

if TYPE_CHECKING:
    from vnpy_ashare.notifications.service import NotificationService


def scan_position_alerts(scan_input: PositionAlertScanInput, service: NotificationService) -> None:
    """扫描持仓异动并触发 position_alert 通知。"""
    if not scan_input.enabled or not scan_input.rows:
        return

    for row in scan_input.rows:
        if not is_position_anomaly(snap=row.snap, quote=row.quote):
            continue
        reasons = position_anomaly_reasons(snap=row.snap, quote=row.quote)
        service.notify(
            NOTIFY_EVENT_POSITION_ALERT,
            dedupe_key=f"{row.vt_symbol}:{','.join(reasons)}",
            payload={
                "vt_symbol": row.vt_symbol,
                "name": row.name,
                "symbol": row.symbol,
                "reasons": format_anomaly_tags(reasons),
                "pnl_pct": row.snap.unrealized_pnl_pct,
                "exit_signal": row.snap.exit_signal,
                "t1_locked": row.snap.t1_locked,
            },
        )
