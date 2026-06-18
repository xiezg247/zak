"""隔日退出共享规则测试。"""

from __future__ import annotations

from vnpy_ashare.domain.trading.exit import ExitRuleHit
from vnpy_ashare.trading.exit.overnight_exit_rules import (
    apply_stop_loss_near_rule,
    apply_stop_loss_pct_rule,
    compute_pnl_pct,
)


def test_compute_pnl_pct() -> None:
    assert compute_pnl_pct(10.0, 9.4) == -6.0


def test_apply_stop_loss_near_uses_loss_wording() -> None:
    rules: list[ExitRuleHit] = []
    warnings: list[str] = []
    apply_stop_loss_near_rule(
        rules,
        warnings,
        pnl_pct=-4.2,
        stop_pct=0.05,
        signal="hold",
    )
    assert len(rules) == 1
    assert "浮亏" in rules[0].detail
    assert "浮盈" not in rules[0].detail


def test_apply_stop_loss_pct_triggers_sell() -> None:
    rules: list[ExitRuleHit] = []
    reasons: list[str] = []
    signal = apply_stop_loss_pct_rule(
        rules,
        reasons,
        pnl_pct=-6.0,
        stop_pct=0.05,
        signal="hold",
    )
    assert signal == "sell"
    assert rules[0].rule_id == "stop_loss_pct"
