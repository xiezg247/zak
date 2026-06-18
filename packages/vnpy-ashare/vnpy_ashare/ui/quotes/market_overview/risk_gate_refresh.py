"""刷新风控闸芯片（自选 / 雷达顶栏）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy_ashare.trading.risk.combined import compute_avg_float_pnl_pct, load_combined_risk_gate_snapshot

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.market_overview.risk_gate_chip import RiskGateChip


def refresh_risk_gate_chip(chip: RiskGateChip, *, page: Any | None = None) -> None:
    position_cache = getattr(page, "position_cache", None) if page is not None else None
    cache = position_cache if isinstance(position_cache, dict) else {}
    avg = compute_avg_float_pnl_pct(cache)
    combined = load_combined_risk_gate_snapshot(
        avg_float_pnl_pct=avg,
        position_cache=cache,
    )
    chip.apply_snapshot(combined)
