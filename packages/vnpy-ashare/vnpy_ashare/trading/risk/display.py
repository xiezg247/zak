"""风控闸展示文案（无 UI 依赖）。"""

from __future__ import annotations

from vnpy_ashare.domain.trading.risk import CombinedRiskGateSnapshot

__all__ = ["build_risk_gate_chip_tooltip", "format_risk_gate_chip_value"]


def format_risk_gate_chip_value(snapshot: CombinedRiskGateSnapshot) -> str:
    account = snapshot.account
    if account.state == "halt":
        return f"{account.state_label} · 停手"
    if not snapshot.allow_new_positions:
        return f"{account.state_label} · 慎开"
    return account.state_label


def build_risk_gate_chip_tooltip(snapshot: CombinedRiskGateSnapshot) -> str:
    account = snapshot.account
    lines = [
        f"账户闸：{account.state_label}",
        "可新开仓" if snapshot.allow_new_positions else "不建议新开仓",
    ]
    if account.daily_pnl_pct is not None:
        lines.append(f"当日盈亏 {account.daily_pnl_pct:+.2f}%")
    if account.avg_float_pnl_pct is not None:
        lines.append(f"持仓浮盈均值 {account.avg_float_pnl_pct:+.2f}%")
    if account.weekly_drawdown_pct is not None:
        lines.append(f"单周回撤 {account.weekly_drawdown_pct:+.2f}%")
    if account.total_drawdown_pct is not None:
        lines.append(f"总回撤 {account.total_drawdown_pct:+.2f}%")
    if account.halt_until:
        lines.append(f"熔断至 {account.halt_until}")
    if snapshot.emotion is not None:
        pos_max = int(snapshot.emotion.position_pct_max * 100)
        lines.append(f"情绪：{snapshot.emotion.stage_label} · 建议≤{pos_max}%")
    if snapshot.actual_position_pct is not None:
        lines.append(f"实际仓位 {snapshot.actual_position_pct * 100:.1f}%")
    for warning in snapshot.warnings[:3]:
        lines.append(warning)
    for warning in account.warnings[:2]:
        if warning not in lines:
            lines.append(warning)
    lines.append("点击打开风控设置")
    return "\n".join(lines)
