"""持仓异动 → 通知扫描。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.notifications.events import NOTIFY_EVENT_POSITION_ALERT
from vnpy_ashare.quotes.misc.position_anomaly import format_anomaly_tags, is_position_anomaly, position_anomaly_reasons

if TYPE_CHECKING:
    from vnpy_ashare.notifications.service import NotificationService
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def scan_watchlist_position_alerts(page: QuotesPage, service: NotificationService) -> None:
    """扫描自选页持仓区异动并触发 position_alert 通知。"""
    if not page.config.show_watchlist_positions or not page.position_cache:
        return

    float_pnls: list[float] = []
    for vt_symbol, snap in page.position_cache.items():
        item = page.find_stock_item(vt_symbol)
        quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
        if not is_position_anomaly(snap=snap, quote=quote):
            continue
        reasons = position_anomaly_reasons(snap=snap, quote=quote)
        if snap.unrealized_pnl_pct is not None:
            float_pnls.append(float(snap.unrealized_pnl_pct))
        name = item.name if item is not None else vt_symbol
        symbol = item.symbol if item is not None else vt_symbol.split(".", 1)[0]
        service.notify(
            NOTIFY_EVENT_POSITION_ALERT,
            dedupe_key=f"{vt_symbol}:{','.join(reasons)}",
            payload={
                "vt_symbol": vt_symbol,
                "name": name,
                "symbol": symbol,
                "reasons": format_anomaly_tags(reasons),
                "pnl_pct": snap.unrealized_pnl_pct,
                "exit_signal": snap.exit_signal,
                "t1_locked": snap.t1_locked,
            },
        )

    if float_pnls:
        avg = sum(float_pnls) / len(float_pnls)
        service.evaluate_risk_gate(avg_float_pnl_pct=avg)
