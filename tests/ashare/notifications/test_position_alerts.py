"""持仓异动通知扫描测试。"""

from __future__ import annotations

from unittest import mock

from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.notifications.core.position_alert_scan import PositionAlertRow, PositionAlertScanInput
from vnpy_ashare.notifications.triggers.position_alerts import scan_position_alerts


def _snap(**kwargs) -> PositionSnapshot:
    defaults = dict(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-10",
        source="manual",
        last_price=9.4,
        market_value=940.0,
        unrealized_pnl=-60.0,
        unrealized_pnl_pct=-6.0,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
        exit_rules=(),
    )
    defaults.update(kwargs)
    return PositionSnapshot(**defaults)  # type: ignore[arg-type]


def test_scan_position_alerts_skips_when_disabled() -> None:
    service = mock.Mock()
    scan_position_alerts(PositionAlertScanInput(enabled=False), service)
    service.notify.assert_not_called()


def test_scan_position_alerts_notifies_anomaly() -> None:
    service = mock.Mock()
    row = PositionAlertRow(
        vt_symbol="600000.SSE",
        name="测试",
        symbol="600000",
        snap=_snap(),
        quote=None,
    )
    with mock.patch(
        "vnpy_ashare.notifications.triggers.position_alerts.is_position_anomaly",
        return_value=True,
    ):
        with mock.patch(
            "vnpy_ashare.notifications.triggers.position_alerts.position_anomaly_reasons",
            return_value=("stop_loss_near",),
        ):
            scan_position_alerts(PositionAlertScanInput(enabled=True, rows=(row,)), service)
    service.notify.assert_called_once()
