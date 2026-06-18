"""隔日退出规则展示（持仓区表格）。"""

from __future__ import annotations

from vnpy_ashare.domain.trading.exit import ExitRuleHit, RuleStatus

_STATUS_LABELS: dict[RuleStatus, str] = {
    "triggered": "触发",
    "near": "临近",
    "clear": "未触发",
}


def format_exit_rules_summary(rules: tuple[ExitRuleHit, ...]) -> str:
    """表格单元格摘要：优先展示触发与临近规则。"""
    if not rules:
        return "—"
    parts: list[str] = []
    for hit in rules:
        if hit.status == "triggered":
            parts.append(hit.label)
        elif hit.status == "near":
            parts.append(f"{hit.label}?")
        if len(parts) >= 3:
            break
    if parts:
        return " · ".join(parts)
    clear_labels = [hit.label for hit in rules if hit.status == "clear"]
    if clear_labels:
        return clear_labels[0]
    return "—"


def format_exit_rules_tooltip(rules: tuple[ExitRuleHit, ...]) -> str:
    if not rules:
        return ""
    lines = [f"{hit.label}（{_STATUS_LABELS.get(hit.status, hit.status)}）：{hit.detail}" for hit in rules]
    return "\n".join(lines)


def exit_rule_cell_color(
    rules: tuple[ExitRuleHit, ...],
    *,
    colors,
    warning_color: str,
) -> str | None:
    """返回表格前景色；无高亮规则时返回 None。"""
    if any(hit.status == "triggered" for hit in rules):
        return str(colors.fall)
    if any(hit.status == "near" for hit in rules):
        return str(warning_color)
    return None
