"""板块近 N 日资金轮动聚合。"""

from __future__ import annotations

from vnpy_ashare.domain.market.flow_pattern import classify_flow_pattern_values
from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowHistoryPoint,
    SectorFlowRotationRow,
    SectorFlowRotationSnapshot,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.domain.time.trade_dates import iter_trade_date_strs
from vnpy_ashare.storage.repositories.sector_flow_history import (
    _ROTATION_DAYS,
    load_sector_flow_matrix,
)

_FLOW_PATTERN_LABELS = ("持续流入", "持续流出", "先出后入", "先入后出", "震荡")


def filter_rotation_rows(
    rows: tuple[SectorFlowRotationRow, ...] | list[SectorFlowRotationRow],
    pattern: str | None,
) -> tuple[SectorFlowRotationRow, ...]:
    """按流动方向标签筛选；空或「全部」返回原序。"""
    cleaned = str(pattern or "").strip()
    if not cleaned or cleaned == "全部":
        return tuple(rows)
    return tuple(row for row in rows if row.flow_pattern == cleaned)


def format_rotation_ai_lines(
    rotation: SectorFlowRotationSnapshot,
    *,
    limit: int = 8,
) -> list[str]:
    """生成轮动摘要行，供 AI 上下文与解读 prompt。"""
    if not rotation.rows:
        return []
    kind_label = "概念" if rotation.sector_kind == "concept" else "行业"
    lines = [f"近15日{kind_label}板块资金轮动（日终口径）："]
    grouped: dict[str, list[SectorFlowRotationRow]] = {}
    for row in rotation.rows:
        grouped.setdefault(row.flow_pattern, []).append(row)
    for pattern in _FLOW_PATTERN_LABELS:
        items = grouped.get(pattern, [])
        if not items:
            continue
        summary = "、".join(f"{item.sector.name}({item.cumulative_net_yi:+.1f}亿)" for item in items[:3])
        lines.append(f"- {pattern}：{summary}")
    for row in rotation.rows[: max(1, limit)]:
        rank_note = ""
        if row.rank_delta:
            direction = "升" if row.rank_delta > 0 else "降"
            rank_note = f"，15日排名{direction}{abs(row.rank_delta)}位"
        lines.append(
            f"· {row.sector.name} {row.flow_pattern} 累计{row.cumulative_net_yi:+.1f}亿 动量Δ{row.momentum_delta:+.1f}亿 净流入{row.positive_days}天{rank_note}"
        )
    return lines


def rotation_trade_dates(*, days: int = _ROTATION_DAYS) -> tuple[str, ...]:
    """近 N 个交易日（升序，与矩阵列头一致）。"""
    dates = list(iter_trade_date_strs(max_lookback=max(1, days)))
    dates.reverse()
    return tuple(dates)


def classify_flow_pattern(points: tuple[SectorFlowHistoryPoint, ...]) -> str:
    if not points:
        return "—"
    return classify_flow_pattern_values([point.net_flow_yi for point in points])


def _align_history_points(
    trade_dates: tuple[str, ...],
    values_by_date: dict[str, float],
) -> tuple[SectorFlowHistoryPoint, ...]:
    return tuple(SectorFlowHistoryPoint(trade_date=trade_date, net_flow_yi=values_by_date.get(trade_date, 0.0)) for trade_date in trade_dates)


def _rank_sectors_on_date(
    matrix: dict[str, dict[str, float]],
    trade_date: str,
    sector_ids: list[str],
) -> dict[str, int]:
    pairs = [(sector_id, matrix.get(sector_id, {}).get(trade_date, 0.0)) for sector_id in sector_ids]
    ordered = sorted(pairs, key=lambda item: item[1], reverse=True)
    return {sector_id: index + 1 for index, (sector_id, _value) in enumerate(ordered)}


def build_rotation_rows(
    snapshot: SectorFlowSnapshot,
    matrix: dict[str, dict[str, float]],
    *,
    trade_dates: tuple[str, ...],
) -> list[SectorFlowRotationRow]:
    sectors: dict[str, SectorFlowRow] = {}
    for row in (*snapshot.inflow_rows, *snapshot.outflow_rows):
        sectors[row.sector_id] = row

    if not sectors or not trade_dates:
        return []

    sector_ids = list(sectors.keys())
    latest_date = trade_dates[-1]
    earliest_date = trade_dates[0]
    rank_now = _rank_sectors_on_date(matrix, latest_date, sector_ids)
    rank_then = _rank_sectors_on_date(matrix, earliest_date, sector_ids)

    rotation_rows: list[SectorFlowRotationRow] = []
    for sector_id, sector in sectors.items():
        points = _align_history_points(trade_dates, matrix.get(sector_id, {}))
        values = [point.net_flow_yi for point in points]
        cumulative = round(sum(values), 2)
        positive_days = sum(1 for value in values if value > 0)
        last_5 = sum(values[-5:])
        first_10 = sum(values[:10]) if len(values) >= 10 else sum(values[:-5]) if len(values) > 5 else 0.0
        momentum_delta = round(last_5 - first_10, 2)
        rank_delta: int | None = None
        if sector_id in rank_now and sector_id in rank_then:
            rank_delta = rank_then[sector_id] - rank_now[sector_id]
        rotation_rows.append(
            SectorFlowRotationRow(
                sector=sector,
                points=points,
                cumulative_net_yi=cumulative,
                positive_days=positive_days,
                flow_pattern=classify_flow_pattern(points),
                momentum_delta=momentum_delta,
                rank_delta=rank_delta,
            )
        )
    rotation_rows.sort(key=lambda item: item.cumulative_net_yi, reverse=True)
    return rotation_rows


def build_rotation_snapshot(
    snapshot: SectorFlowSnapshot,
    *,
    days: int = _ROTATION_DAYS,
) -> SectorFlowRotationSnapshot:
    kind = snapshot.sector_kind or "industry"
    trade_dates = rotation_trade_dates(days=days)
    sector_ids = [row.sector_id for row in (*snapshot.inflow_rows, *snapshot.outflow_rows)]
    matrix = load_sector_flow_matrix(
        sector_kind=kind,
        trade_dates=list(trade_dates),
        sector_ids=sector_ids,
    )
    rows = build_rotation_rows(snapshot, matrix, trade_dates=trade_dates)

    empty_hint = ""
    if not snapshot.rows:
        empty_hint = snapshot.empty_hint or "暂无板块数据"
    elif not rows:
        empty_hint = "暂无近15日轮动数据。请收盘后运行「板块资金同步」任务。"
    elif snapshot.data_mode == "intraday":
        empty_hint = "盘中为估算口径；近15日轮动以日终官方数据为准，收盘同步后更准确。"

    updated_at = snapshot.updated_at or ""
    if updated_at and "近15日" not in updated_at:
        updated_at = f"{updated_at} · 近{days}日轮动"

    return SectorFlowRotationSnapshot(
        trade_dates=trade_dates,
        rows=tuple(rows),
        sector_kind=kind,
        updated_at=updated_at,
        empty_hint=empty_hint,
        data_mode=snapshot.data_mode if snapshot.data_mode != "intraday" else "official_dc",
    )


__all__ = [
    "classify_flow_pattern",
    "build_rotation_rows",
    "build_rotation_snapshot",
    "rotation_trade_dates",
    "filter_rotation_rows",
    "format_rotation_ai_lines",
    "FLOW_PATTERN_LABELS",
]

FLOW_PATTERN_LABELS = _FLOW_PATTERN_LABELS
