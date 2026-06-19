"""板块未来 N 日展望 A/B 对照。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookCompareRow,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
)


def _day_bias(row: SectorFlowOutlookRow | None, *, day_index: int = 0) -> str:
    if row is None or not row.days or day_index >= len(row.days):
        return ""
    return row.days[day_index].bias


def classify_outlook_agreement(
    continuation: SectorFlowOutlookRow | None,
    strategy: SectorFlowOutlookRow | None,
    *,
    day_index: int = 0,
) -> str:
    cont_bias = _day_bias(continuation, day_index=day_index)
    strat_bias = _day_bias(strategy, day_index=day_index)
    if cont_bias and strat_bias:
        return "一致" if cont_bias == strat_bias else "分歧"
    if cont_bias:
        return "仅延续"
    if strat_bias:
        return "仅策略"
    return "—"


def build_outlook_compare_rows(
    continuation: SectorFlowOutlookSnapshot,
    strategy: SectorFlowOutlookSnapshot,
) -> tuple[SectorFlowOutlookCompareRow, ...]:
    cont_map = {row.sector.sector_id: row for row in continuation.rows}
    strat_map = {row.sector.sector_id: row for row in strategy.rows}
    sector_ids = list(dict.fromkeys([*cont_map.keys(), *strat_map.keys()]))

    rows: list[SectorFlowOutlookCompareRow] = []
    for sector_id in sector_ids:
        cont_row = cont_map.get(sector_id)
        strat_row = strat_map.get(sector_id)
        sector = (cont_row or strat_row).sector if (cont_row or strat_row) else None
        if sector is None:
            continue
        rows.append(
            SectorFlowOutlookCompareRow(
                sector=sector,
                continuation=cont_row,
                strategy=strat_row,
                agreement=classify_outlook_agreement(cont_row, strat_row),
            )
        )

    def _sort_key(item: SectorFlowOutlookCompareRow) -> tuple:
        agreement_rank = {"一致": 0, "分歧": 1, "仅延续": 2, "仅策略": 3, "—": 4}
        cont_strength = item.continuation.days[0].strength if item.continuation and item.continuation.days else 0.0
        strat_strength = item.strategy.days[0].strength if item.strategy and item.strategy.days else 0.0
        return (
            agreement_rank.get(item.agreement, 9),
            -(cont_strength + strat_strength),
            item.sector.name,
        )

    rows.sort(key=_sort_key)
    return tuple(rows)


def filter_compare_rows(
    rows: tuple[SectorFlowOutlookCompareRow, ...] | list[SectorFlowOutlookCompareRow],
    agreement: str | None,
) -> tuple[SectorFlowOutlookCompareRow, ...]:
    cleaned = str(agreement or "").strip()
    if not cleaned or cleaned == "全部":
        return tuple(rows)
    return tuple(row for row in rows if row.agreement == cleaned)


def format_compare_ai_lines(
    continuation: SectorFlowOutlookSnapshot,
    strategy: SectorFlowOutlookSnapshot,
    compare_rows: tuple[SectorFlowOutlookCompareRow, ...],
    *,
    limit: int = 8,
) -> list[str]:
    from vnpy_ashare.services.sector_flow_outlook import format_continuation_ai_lines
    from vnpy_ashare.services.sector_flow_outlook_strategy import format_strategy_ai_lines

    lines = format_continuation_ai_lines(continuation, limit=limit)
    lines.extend(format_strategy_ai_lines(strategy, limit=limit))
    agreed = [row.sector.name for row in compare_rows if row.agreement == "一致"][:5]
    diverged = [row.sector.name for row in compare_rows if row.agreement == "分歧"][:5]
    if agreed:
        lines.append("延续与策略一致：" + "、".join(agreed))
    if diverged:
        lines.append("延续与策略分歧：" + "、".join(diverged))
    return lines


__all__ = [
    "build_outlook_compare_rows",
    "classify_outlook_agreement",
    "filter_compare_rows",
    "format_compare_ai_lines",
]
