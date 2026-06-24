"""浮亏扛单判定（纯持仓快照，不写流水）。"""

from __future__ import annotations

from collections.abc import Mapping

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
from vnpy_ashare.domain.trading.position import PositionSnapshot

__all__ = ["float_loss_threshold_pct", "is_float_loss_hold", "scan_float_loss_holds"]


def float_loss_threshold_pct() -> float:
    prefs = load_trading_risk_prefs()
    return float(prefs.caution_float_pct)


def is_float_loss_hold(
    snap: PositionSnapshot,
    *,
    threshold_pct: float | None = None,
) -> bool:
    if snap.unrealized_pnl_pct is None:
        return False
    threshold = threshold_pct if threshold_pct is not None else float_loss_threshold_pct()
    return float(snap.unrealized_pnl_pct) <= threshold


def scan_float_loss_holds(
    position_cache: Mapping[str, PositionSnapshot] | None,
) -> list[str]:
    if not position_cache:
        return []
    return [vt for vt, snap in position_cache.items() if is_float_loss_hold(snap)]
