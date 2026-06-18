"""持仓隔日退出规则叠加。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.strategy_profile import load_strategy_profile_id
from vnpy_ashare.domain.trading.position import PositionRecord, PositionSnapshot
from vnpy_ashare.trading.exit.overnight_exit import evaluate_overnight_exit

if TYPE_CHECKING:
    from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot


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
    exit_rules = evaluation.rules

    base_signal = snapshot.signal_snapshot
    if evaluation.signal == "sell" and base_signal is not None:
        rule_lines = [f"{hit.label}：{hit.detail}" for hit in evaluation.rules if hit.status == "triggered"]
        reasons = tuple(dict.fromkeys((*base_signal.reasons, *evaluation.reasons, *rule_lines)))
        base_signal = base_signal.model_copy(
            update={
                "strategy_id": "AshareOvernightExitStrategy",
                "signal": "sell",
                "signal_label": "卖出",
                "ref_sell_price": evaluation.ref_sell_price or base_signal.ref_sell_price,
                "reason_summary": "隔日退出",
                "reasons": reasons,
                "warnings": merged_warnings,
                "action_ref_sell_price": evaluation.ref_sell_price or base_signal.action_ref_sell_price,
            }
        )
        exit_signal = "sell"
    elif evaluation.warnings and base_signal is not None:
        base_signal = base_signal.model_copy(update={"warnings": merged_warnings})
    elif evaluation.rules and base_signal is not None and evaluation.signal == "hold":
        rule_lines = [f"{hit.label}：{hit.detail}" for hit in evaluation.rules if hit.status in ("triggered", "near")]
        if rule_lines:
            reasons = tuple(dict.fromkeys((*base_signal.reasons, *rule_lines)))
            base_signal = base_signal.model_copy(update={"reasons": reasons})

    return snapshot.model_copy(
        update={
            "exit_signal": exit_signal,
            "signal_snapshot": base_signal,
            "exit_ref_price": evaluation.ref_sell_price or snapshot.exit_ref_price,
            "warnings": merged_warnings,
            "exit_rules": exit_rules,
        }
    )
