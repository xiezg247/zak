"""连板梯队日切：快照构建与断板率 / 昨高板跌停判定。"""

from __future__ import annotations

from vnpy_ashare.domain.symbols.stock import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.storage.repositories.emotion_ladder_daily import (
    EmotionLadderDailySnapshot,
    load_previous_ladder_snapshot,
    save_ladder_snapshot,
    today_trade_date_iso,
)

__all__ = [
    "build_ladder_snapshot_from_map",
    "compute_ladder_continuity",
    "limit_down_threshold_pct",
    "maybe_persist_ladder_snapshot",
]


def limit_down_threshold_pct(vt_symbol: str) -> float:
    symbol = vt_symbol.split(".")[0]
    if symbol.startswith(("300", "688")):
        return -19.5
    return -9.5


def _boards_by_vt_symbol(limit_times_map: dict[str, float]) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, raw in limit_times_map.items():
        boards = int(raw or 0)
        if boards < 1:
            continue
        item = parse_tickflow_symbol(key) or parse_stock_symbol(key)
        if item is None:
            continue
        prev = result.get(item.vt_symbol, 0)
        if boards > prev:
            result[item.vt_symbol] = boards
    return result


def build_ladder_snapshot_from_map(
    limit_times_map: dict[str, float],
    *,
    trade_date: str | None = None,
) -> EmotionLadderDailySnapshot | None:
    boards_by_vt = _boards_by_vt_symbol(limit_times_map)
    if not boards_by_vt:
        return None
    max_boards = max(boards_by_vt.values())
    max_vt = sorted(vt for vt, boards in boards_by_vt.items() if boards == max_boards)[0]
    linked = tuple(sorted(vt for vt, boards in boards_by_vt.items() if boards >= 2))
    return EmotionLadderDailySnapshot(
        trade_date=(trade_date or today_trade_date_iso())[:10],
        max_limit_times=max_boards,
        max_board_vt_symbol=max_vt,
        linked_board_vt_symbols=linked,
        board_counts=dict(boards_by_vt),
        updated_at=format_china_datetime(),
    )


def maybe_persist_ladder_snapshot(limit_times_map: dict[str, float], *, trade_date: str | None = None) -> None:
    snapshot = build_ladder_snapshot_from_map(limit_times_map, trade_date=trade_date)
    if snapshot is not None:
        save_ladder_snapshot(snapshot)


def _quote_change_by_vt() -> dict[str, float]:
    result: dict[str, float] = {}
    for vt_symbol, row in quote_rows_by_vt_symbol().items():
        change = row.change_pct
        if change is not None:
            result[vt_symbol] = float(change)
    return result


def compute_ladder_continuity(
    *,
    trade_date: str | None = None,
    limit_times_map: dict[str, float],
    quote_change_by_vt: dict[str, float] | None = None,
) -> tuple[float | None, bool, int | None]:
    """返回 (断板率 0–1, 昨最高板今日跌停, 昨最高连板数)。"""
    day = (trade_date or today_trade_date_iso())[:10]
    prev = load_previous_ladder_snapshot(day)
    if prev is None:
        return None, False, None

    today_boards = _boards_by_vt_symbol(limit_times_map)
    changes = quote_change_by_vt if quote_change_by_vt is not None else _quote_change_by_vt()

    pool = prev.board_counts or {vt: 2 for vt in prev.linked_board_vt_symbols}
    tracked = {vt: boards for vt, boards in pool.items() if boards >= 2}
    if not tracked:
        tracked = {vt: 2 for vt in prev.linked_board_vt_symbols}
    if not tracked:
        return None, False, prev.max_limit_times or None

    broken = 0
    for vt, prev_boards in tracked.items():
        today = today_boards.get(vt, 0)
        change = changes.get(vt)
        if today >= prev_boards:
            continue
        if change is not None and change <= limit_down_threshold_pct(vt):
            broken += 1
            continue
        if today < 1:
            broken += 1

    break_rate = broken / len(tracked)

    prev_leader_limit_down = False
    if prev.max_board_vt_symbol:
        leader = prev.max_board_vt_symbol
        change = changes.get(leader)
        threshold = limit_down_threshold_pct(leader)
        if change is not None and change <= threshold:
            prev_leader_limit_down = True

    prev_max = prev.max_limit_times if prev.max_limit_times > 0 else None
    return break_rate, prev_leader_limit_down, prev_max


def is_limit_down_change(vt_symbol: str, change_pct: float) -> bool:
    return change_pct <= limit_down_threshold_pct(vt_symbol)
