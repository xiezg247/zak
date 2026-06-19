"""板块未来 N 日资金展望：统计延续口径（A）。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import (
    OUTLOOK_DISCLAIMER,
    OUTLOOK_HORIZON_DAYS,
    SectorFlowOutlookDay,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRotationRow,
    SectorFlowRotationSnapshot,
    SectorFlowSnapshot,
)
from vnpy_ashare.domain.time.trade_dates import iter_forward_trade_date_strs
from vnpy_ashare.services.sector_flow_rotation import build_rotation_snapshot

_OUTLOOK_BIAS_LABELS = ("偏多", "偏空", "震荡")

_PATTERN_BIAS_SEQUENCE: dict[str, tuple[str, str, str]] = {
    "持续流入": ("偏多", "偏多", "震荡"),
    "持续流出": ("偏空", "偏空", "震荡"),
    "先出后入": ("震荡", "偏多", "偏多"),
    "先入后出": ("偏多", "震荡", "偏空"),
    "震荡": ("震荡", "震荡", "震荡"),
}

_PATTERN_BASE_STRENGTH: dict[str, float] = {
    "持续流入": 0.72,
    "持续流出": 0.72,
    "先出后入": 0.58,
    "先入后出": 0.58,
    "震荡": 0.42,
}

_HORIZON_DECAY = (1.0, 0.72, 0.50)
_STRENGTH_NEUTRAL_THRESHOLD = 0.35


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _continuation_day_rows(
    rotation_row: SectorFlowRotationRow,
    forward_dates: tuple[str, ...],
) -> tuple[SectorFlowOutlookDay, ...]:
    pattern = rotation_row.flow_pattern
    base_seq = _PATTERN_BIAS_SEQUENCE.get(pattern, ("震荡", "震荡", "震荡"))
    base_strength = _PATTERN_BASE_STRENGTH.get(pattern, 0.42)
    momentum_boost = _clamp(rotation_row.momentum_delta / 10.0, -0.15, 0.15)
    rank_boost = _clamp((rotation_row.rank_delta or 0) / 10.0, -0.10, 0.10)
    core = base_strength + momentum_boost + rank_boost

    days: list[SectorFlowOutlookDay] = []
    for index, trade_date in enumerate(forward_dates):
        decay = _HORIZON_DECAY[index] if index < len(_HORIZON_DECAY) else _HORIZON_DECAY[-1]
        strength = _clamp(core * decay, 0.0, 1.0)
        bias = base_seq[index] if index < len(base_seq) else "震荡"
        if strength < _STRENGTH_NEUTRAL_THRESHOLD:
            bias = "震荡"
        days.append(
            SectorFlowOutlookDay(
                trade_date=trade_date,
                bias=bias,
                strength=round(strength, 2),
            )
        )
    return tuple(days)


def _continuation_rationale(rotation_row: SectorFlowRotationRow) -> str:
    pattern = rotation_row.flow_pattern
    rank_note = ""
    if rotation_row.rank_delta:
        direction = "升" if rotation_row.rank_delta > 0 else "降"
        rank_note = f"，15日排名{direction}{abs(rotation_row.rank_delta)}位"
    return f"{pattern}，动量Δ{rotation_row.momentum_delta:+.1f}亿，15日累计{rotation_row.cumulative_net_yi:+.1f}亿{rank_note}"


def build_continuation_outlook(
    rotation: SectorFlowRotationSnapshot,
    *,
    horizon_days: int = OUTLOOK_HORIZON_DAYS,
) -> SectorFlowOutlookSnapshot:
    forward_dates = iter_forward_trade_date_strs(count=horizon_days)
    rows: list[SectorFlowOutlookRow] = []
    cumulative_map = {item.sector.sector_id: item.cumulative_net_yi for item in rotation.rows}
    for rotation_row in rotation.rows:
        days = _continuation_day_rows(rotation_row, forward_dates)
        rows.append(
            SectorFlowOutlookRow(
                sector=rotation_row.sector,
                days=days,
                headline_pattern=rotation_row.flow_pattern,
                rationale=_continuation_rationale(rotation_row),
                source="continuation",
            )
        )
    rows.sort(
        key=lambda item: (
            -(item.days[0].strength if item.days else 0.0),
            -cumulative_map.get(item.sector.sector_id, 0.0),
            item.sector.name,
        )
    )

    empty_hint = rotation.empty_hint
    if not rotation.rows and not empty_hint:
        empty_hint = "暂无近15日轮动数据，无法生成延续展望。"

    updated_at = rotation.updated_at or ""
    if updated_at and "未来3日" not in updated_at:
        updated_at = f"{updated_at} · 未来{horizon_days}日延续"

    return SectorFlowOutlookSnapshot(
        forward_dates=forward_dates,
        rows=tuple(rows),
        sector_kind=rotation.sector_kind,
        source="continuation",
        updated_at=updated_at,
        empty_hint=empty_hint,
        disclaimer=OUTLOOK_DISCLAIMER,
        data_mode=rotation.data_mode,
    )


def build_continuation_outlook_snapshot(
    snapshot: SectorFlowSnapshot,
    *,
    horizon_days: int = OUTLOOK_HORIZON_DAYS,
) -> SectorFlowOutlookSnapshot:
    rotation = build_rotation_snapshot(snapshot)
    return build_continuation_outlook(rotation, horizon_days=horizon_days)


def filter_outlook_rows(
    rows: tuple[SectorFlowOutlookRow, ...] | list[SectorFlowOutlookRow],
    bias: str | None,
    *,
    day_index: int = 0,
) -> tuple[SectorFlowOutlookRow, ...]:
    cleaned = str(bias or "").strip()
    if not cleaned or cleaned == "全部":
        return tuple(rows)
    filtered: list[SectorFlowOutlookRow] = []
    for row in rows:
        if not row.days or day_index >= len(row.days):
            continue
        if row.days[day_index].bias == cleaned:
            filtered.append(row)
    return tuple(filtered)


def format_continuation_ai_lines(
    outlook: SectorFlowOutlookSnapshot,
    *,
    limit: int = 8,
) -> list[str]:
    if not outlook.rows:
        return []
    kind_label = "概念" if outlook.sector_kind == "concept" else "行业"
    lines = [f"未来{len(outlook.forward_dates)}日{kind_label}资金延续展望（{outlook.disclaimer}）："]
    for row in outlook.rows[: max(1, limit)]:
        day_tags = " / ".join(f"T+{index + 1}{day.bias}" for index, day in enumerate(row.days))
        lines.append(f"· {row.sector.name} {row.headline_pattern} {day_tags} — {row.rationale}")
    return lines


__all__ = [
    "OUTLOOK_BIAS_LABELS",
    "build_continuation_outlook",
    "build_continuation_outlook_snapshot",
    "filter_outlook_rows",
    "format_continuation_ai_lines",
]

OUTLOOK_BIAS_LABELS = _OUTLOOK_BIAS_LABELS
