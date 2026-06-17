"""计划仓位 vs 记账仓位（P-04 / P-07）。"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.domain.trading.position import PositionRecord, PositionSnapshot


def normalize_plan_pct(value: float | None) -> float | None:
    """归一化计划占比（0–1）；无效值视为未设定。"""
    if value is None:
        return None
    pct = float(value)
    if pct <= 0 or pct > 1:
        return None
    return round(pct, 4)


def compute_position_actual_pct(
    *,
    market_value: float | None,
    total_capital: float | None,
) -> float | None:
    if total_capital is None or total_capital <= 0:
        return None
    if market_value is None or market_value <= 0:
        return 0.0
    return round(market_value / total_capital, 4)


def sum_plan_pct(records: list[PositionRecord]) -> float | None:
    values = [pct for record in records if (pct := normalize_plan_pct(record.plan_pct)) is not None]
    if not values:
        return None
    return round(sum(values), 4)


class GroupPositionSummary(FrozenModel):
    group_id: str = Field(description="分组 ID")
    position_count: int = Field(description="持仓数量")
    actual_pct: float | None = Field(description="实际仓位占比（0–1）")
    plan_cap_pct: float | None = Field(description="计划仓位上限（0–1）")
    plan_pct_sum: float | None = Field(description="计划占比合计（0–1）")
    over_cap: bool = Field(description="是否超出上限")


def summarize_group_position(
    *,
    group_id: str,
    member_keys: set[tuple[str, str]],
    records: list[PositionRecord],
    position_cache: Mapping[str, PositionSnapshot] | None,
    total_capital: float | None,
    position_cap_pct: float | None,
) -> GroupPositionSummary:
    cap = normalize_plan_pct(position_cap_pct)
    matched = [record for record in records if (record.symbol, record.exchange) in member_keys]
    cache = position_cache or {}
    total_mv = 0.0
    has_mv = False
    plan_values: list[float] = []
    for record in matched:
        plan = normalize_plan_pct(record.plan_pct)
        if plan is not None:
            plan_values.append(plan)
        snap = cache.get(record.vt_symbol)
        if snap is not None and snap.market_value is not None and snap.market_value > 0:
            total_mv += snap.market_value
            has_mv = True
    actual = None
    if total_capital is not None and total_capital > 0:
        actual = round(total_mv / total_capital, 4) if has_mv else 0.0
    plan_sum = round(sum(plan_values), 4) if plan_values else None
    over_cap = False
    if cap is not None and actual is not None and actual > cap + 1e-9:
        over_cap = True
    return GroupPositionSummary(
        group_id=group_id,
        position_count=len(matched),
        actual_pct=actual,
        plan_cap_pct=cap,
        plan_pct_sum=plan_sum,
        over_cap=over_cap,
    )


def format_pct_int(fraction: float | None) -> str | None:
    if fraction is None:
        return None
    return str(int(round(fraction * 100)))


def format_group_position_tab_suffix(summary: GroupPositionSummary) -> str | None:
    actual_text = format_pct_int(summary.actual_pct)
    if actual_text is None:
        return None
    cap_text = format_pct_int(summary.plan_cap_pct)
    if cap_text is not None:
        return f"{actual_text}/{cap_text}%"
    return f"{actual_text}%"


def format_group_position_tab_label(name: str, summary: GroupPositionSummary | None) -> str:
    if summary is None:
        return name
    suffix = format_group_position_tab_suffix(summary)
    if suffix is None:
        return name
    return f"{name} {suffix}"


def format_plan_position_hint(
    *,
    actual_pct: float | None,
    plan_pct_sum: float | None,
) -> str | None:
    parts: list[str] = []
    if plan_pct_sum is not None:
        parts.append(f"计划 Σ {int(round(plan_pct_sum * 100))}%")
    if actual_pct is not None:
        parts.append(f"实际 {int(round(actual_pct * 100))}%")
    if not parts:
        return None
    return " · ".join(parts)


def format_plan_vs_actual_cell(
    *,
    plan_pct: float | None,
    actual_pct: float | None,
) -> tuple[str, str]:
    plan = normalize_plan_pct(plan_pct)
    actual_text = format_pct_int(actual_pct)
    if plan is None and actual_text is None:
        return "—", ""
    plan_text = format_pct_int(plan) if plan is not None else "—"
    if actual_text is None:
        return f"{plan_text}%", "计划仓位占比（相对总资金）"
    tooltip = f"计划 {plan_text}% · 实际 {actual_text}%"
    if plan is not None and actual_pct is not None:
        delta = int(round((actual_pct - plan) * 100))
        if delta > 0:
            tooltip += f"（超计划 {delta}%）"
        elif delta < 0:
            tooltip += f"（低于计划 {-delta}%）"
    return f"{plan_text}/{actual_text}%", tooltip
