"""自选多维看盘 AI 摘要。"""

from __future__ import annotations

from collections.abc import Mapping

from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiRow


def build_multiview_board_summary(
    rows: tuple[WatchlistMultiRow, ...],
    *,
    signal_symbols: set[str] | frozenset[str] | None = None,
    signal_cache: Mapping[str, SignalSnapshot] | None = None,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
) -> str:
    if not rows:
        return ""

    signal_symbols = signal_symbols or frozenset()
    signal_cache = signal_cache or {}
    position_cache = position_cache or {}

    rise = sum(1 for row in rows if (row.change_pct or 0) > 0)
    fall = sum(1 for row in rows if (row.change_pct or 0) < 0)
    flat = len(rows) - rise - fall
    parts = [f"自选多维：共 {len(rows)} 只，涨 {rise} / 跌 {fall} / 平 {flat}"]

    signal_counts: dict[str, int] = {}
    for vt in signal_symbols:
        snap = signal_cache.get(vt)
        if snap is None or snap.signal == "na":
            continue
        label = snap.signal_label or snap.signal
        signal_counts[label] = signal_counts.get(label, 0) + 1
    if signal_counts:
        detail = " ".join(f"{count}{label}" for label, count in sorted(signal_counts.items()))
        parts.append(f"信号区 {detail}")

    pnl_values = [pos.unrealized_pnl_pct for pos in position_cache.values() if pos.unrealized_pnl_pct is not None]
    if pnl_values:
        avg_pnl = sum(pnl_values) / len(pnl_values)
        parts.append(f"持仓 {len(pnl_values)} 只，均浮盈 {avg_pnl:+.2f}%")

    hot = sorted(rows, key=lambda row: row.anomaly_score, reverse=True)[:3]
    if hot and hot[0].anomaly_score >= 8.0:
        samples: list[str] = []
        for row in hot:
            if row.change_pct is not None:
                samples.append(f"{row.name}({row.change_pct:+.2f}%)")
            else:
                samples.append(row.name)
        parts.append(f"异动前列：{'、'.join(samples)}")

    return "；".join(parts)
