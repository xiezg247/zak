"""短线观察分组：ensure + 批量写入（D-04）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData, RadarRow
from vnpy_ashare.services.watchlist_service import WatchlistService

SHORT_TERM_OBSERVATION_GROUP_NAME = "短线观察"


def find_short_term_observation_group_id(service: WatchlistService) -> str | None:
    for group in service.list_groups():
        if group.name == SHORT_TERM_OBSERVATION_GROUP_NAME:
            return group.id
    return None


def ensure_short_term_observation_group(service: WatchlistService) -> tuple[str | None, bool]:
    """返回 (group_id, 是否新建分组)。"""
    existing = find_short_term_observation_group_id(service)
    if existing:
        return existing, False
    created = service.create_group(SHORT_TERM_OBSERVATION_GROUP_NAME)
    return created, created is not None


@dataclass(frozen=True)
class ShortTermObservationBatchResult:
    watchlist_added: int
    group_added: int
    skipped: int
    group_created: bool


def add_rows_to_short_term_observation_group(
    service: WatchlistService,
    rows: tuple[RadarRow, ...] | list[RadarRow],
) -> ShortTermObservationBatchResult:
    """先确保在自选池，再写入「短线观察」分组。"""
    group_id, group_created = ensure_short_term_observation_group(service)
    if group_id is None:
        return ShortTermObservationBatchResult(0, 0, len(rows), False)

    existing_members = service.group_member_keys(group_id)
    watchlist_added = group_added = skipped = 0
    for row in rows:
        item = parse_stock_symbol(row.vt_symbol)
        if item is None:
            skipped += 1
            continue
        key = (item.symbol, item.exchange.name)
        name = row.name or item.name
        if service.add(item.symbol, item.exchange, name):
            watchlist_added += 1
        elif service.add_failure_reason(item.symbol, item.exchange) == "full":
            skipped += 1
            break
        if key in existing_members:
            skipped += 1
            continue
        if service.add_to_group(group_id, item.symbol, item.exchange):
            existing_members.add(key)
            group_added += 1
        else:
            skipped += 1
    return ShortTermObservationBatchResult(
        watchlist_added=watchlist_added,
        group_added=group_added,
        skipped=skipped,
        group_created=group_created,
    )


def collect_dragon_1_rows(payload: dict[str, RadarCardData]) -> tuple[RadarRow, ...]:
    data = payload.get("leader_pick")
    if data is None:
        return ()
    return tuple(row for row in data.rows if row.leader_tier == "dragon_1")


def _radar_row_from_screener_dict(row: dict) -> RadarRow | None:
    from vnpy_ashare.domain.symbols import parse_stock_symbol

    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    name = str(row.get("name") or (item.name if item else "") or vt_symbol)
    symbol = str(row.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=None,
        change_pct=None,
        metric_label="",
        metric_value="",
        sub_label="",
        sub_value="",
    )


def add_screener_rows_to_short_term_observation_group(
    service: WatchlistService,
    rows: list[dict],
) -> ShortTermObservationBatchResult:
    parsed: list[RadarRow] = []
    for row in rows:
        item = _radar_row_from_screener_dict(row)
        if item is not None:
            parsed.append(item)
    return add_rows_to_short_term_observation_group(service, parsed)
