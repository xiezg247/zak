"""持仓隔日退出规则叠加。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.strategy_profile import load_strategy_profile_id
from vnpy_ashare.domain.position_snapshot import PositionRecord, PositionSnapshot
from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
from vnpy_ashare.trading.exit.overnight_exit import evaluate_overnight_exit

if TYPE_CHECKING:
    from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot


def apply_overnight_exit_overlay(
    record: PositionRecord,
    snapshot: PositionSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
) -> PositionSnapshot:
    if load_strategy_profile_id() != "ultra_short":
        return snapshot

    evaluation = evaluate_overnight_exit(record, quote=quote)
    merged_warnings = tuple(dict.fromkeys((*snapshot.warnings, *evaluation.warnings)))
    exit_signal = evaluation.signal if evaluation.signal != "na" else snapshot.exit_signal

    base_signal = snapshot.signal_snapshot
    if evaluation.signal == "sell" and base_signal is not None:
        rule_lines = [f"{hit.label}：{hit.detail}" for hit in evaluation.rules if hit.status == "triggered"]
        reasons = tuple(dict.fromkeys((*base_signal.reasons, *evaluation.reasons, *rule_lines)))
        base_signal = SignalSnapshot(
            vt_symbol=base_signal.vt_symbol,
            strategy_id="AshareOvernightExitStrategy",
            as_of=base_signal.as_of,
            signal="sell",
            signal_label="卖出",
            signal_date=base_signal.signal_date,
            ref_buy_price=base_signal.ref_buy_price,
            ref_sell_price=evaluation.ref_sell_price or base_signal.ref_sell_price,
            strength=base_signal.strength,
            reason_summary="隔日退出",
            reasons=reasons,
            warnings=merged_warnings,
            last_close=base_signal.last_close,
            action_ref_buy_price=base_signal.action_ref_buy_price,
            action_ref_sell_price=evaluation.ref_sell_price or base_signal.action_ref_sell_price,
            fast_ma=base_signal.fast_ma,
            slow_ma=base_signal.slow_ma,
            volume_ratio_5d=base_signal.volume_ratio_5d,
            ma_gap_pct=base_signal.ma_gap_pct,
            strength_cross=base_signal.strength_cross,
            strength_alignment=base_signal.strength_alignment,
            strength_volume=base_signal.strength_volume,
            strength_pattern=base_signal.strength_pattern,
            relative_index_pct=base_signal.relative_index_pct,
        )
        exit_signal = "sell"
    elif evaluation.warnings and base_signal is not None:
        base_signal = replace(base_signal, warnings=merged_warnings)

    return PositionSnapshot(
        vt_symbol=snapshot.vt_symbol,
        name=snapshot.name,
        cost_price=snapshot.cost_price,
        volume=snapshot.volume,
        buy_date=snapshot.buy_date,
        source=snapshot.source,
        last_price=snapshot.last_price,
        market_value=snapshot.market_value,
        unrealized_pnl=snapshot.unrealized_pnl,
        unrealized_pnl_pct=snapshot.unrealized_pnl_pct,
        exit_signal=exit_signal,
        signal_snapshot=base_signal,
        t1_locked=snapshot.t1_locked,
        exit_ref_price=evaluation.ref_sell_price or snapshot.exit_ref_price,
        dist_exit_pct=snapshot.dist_exit_pct,
        warnings=merged_warnings,
    )
