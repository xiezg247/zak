"""情绪周期连板梯队日切快照（P0-3）。"""

from __future__ import annotations

import json
from datetime import date

from pydantic import Field

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_ashare.storage.repositories.trade_calendar import previous_open_trading_day
from vnpy_common.domain.base import FrozenModel

__all__ = [
    "EmotionLadderDailySnapshot",
    "load_ladder_snapshot",
    "load_previous_ladder_snapshot",
    "save_ladder_snapshot",
    "today_trade_date_iso",
]


class EmotionLadderDailySnapshot(FrozenModel):
    trade_date: str = Field(description="交易日 YYYY-MM-DD")
    max_limit_times: int = Field(default=0, description="当日最高连板")
    max_board_vt_symbol: str = Field(default="", description="最高连板 vt_symbol")
    linked_board_vt_symbols: tuple[str, ...] = Field(default=(), description="≥2 板 vt_symbol 列表")
    board_counts: dict[str, int] = Field(default_factory=dict, description="vt_symbol → 连板数")
    updated_at: str = Field(default="", description="写入时间")


def today_trade_date_iso() -> str:
    return date.today().isoformat()


def save_ladder_snapshot(snapshot: EmotionLadderDailySnapshot) -> None:
    init_app_db()
    payload = json.dumps(list(snapshot.linked_board_vt_symbols), ensure_ascii=False)
    counts_payload = json.dumps(snapshot.board_counts, ensure_ascii=False)
    updated_at = snapshot.updated_at or format_china_datetime()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO emotion_limit_ladder_daily(
                trade_date, max_limit_times, max_board_vt_symbol, linked_board_vt_symbols, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(trade_date) DO UPDATE SET
                max_limit_times = excluded.max_limit_times,
                max_board_vt_symbol = excluded.max_board_vt_symbol,
                linked_board_vt_symbols = excluded.linked_board_vt_symbols,
                updated_at = excluded.updated_at
            """,
            (
                snapshot.trade_date[:10],
                int(snapshot.max_limit_times),
                snapshot.max_board_vt_symbol,
                payload,
                updated_at,
            ),
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (f"emotion_ladder_counts:{snapshot.trade_date[:10]}", counts_payload),
        )


def load_ladder_snapshot(trade_date: str) -> EmotionLadderDailySnapshot | None:
    init_app_db()
    day = trade_date[:10]
    with connect() as conn:
        row = conn.execute(
            """
            SELECT trade_date, max_limit_times, max_board_vt_symbol, linked_board_vt_symbols, updated_at
            FROM emotion_limit_ladder_daily WHERE trade_date = ?
            """,
            (day,),
        ).fetchone()
        if row is None:
            return None
        counts_row = conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (f"emotion_ladder_counts:{day}",),
        ).fetchone()
    counts_raw = counts_row["value"] if counts_row is not None else None
    try:
        linked = tuple(json.loads(str(row["linked_board_vt_symbols"] or "[]")))
    except json.JSONDecodeError:
        linked = ()
    if counts_raw:
        try:
            parsed = json.loads(str(counts_raw))
            if isinstance(parsed, dict):
                board_counts = {str(k): int(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            board_counts = {}
    return EmotionLadderDailySnapshot(
        trade_date=str(row["trade_date"]),
        max_limit_times=int(row["max_limit_times"] or 0),
        max_board_vt_symbol=str(row["max_board_vt_symbol"] or ""),
        linked_board_vt_symbols=linked,
        board_counts=board_counts,
        updated_at=str(row["updated_at"] or ""),
    )


def load_previous_ladder_snapshot(trade_date: str | None = None) -> EmotionLadderDailySnapshot | None:
    current = date.fromisoformat((trade_date or today_trade_date_iso())[:10])
    prev = previous_open_trading_day(current)
    if prev is None:
        return None
    return load_ladder_snapshot(prev.isoformat())
