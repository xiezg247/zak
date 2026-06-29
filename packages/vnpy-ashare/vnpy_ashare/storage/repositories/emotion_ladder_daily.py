"""情绪周期连板梯队日切快照（P0-3）。"""

from __future__ import annotations

import json
from datetime import date

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.repositories.trade_calendar import previous_open_trading_day
from vnpy_ashare.storage.repository.app import AppBaseRepository, MetaRepository
from vnpy_common.domain.base import FrozenModel
from vnpy_common.storage.tables import emotion_limit_ladder_daily as eld
from vnpy_common.storage.tables import meta

__all__ = [
    "EmotionLadderDailySnapshot",
    "load_ladder_snapshot",
    "load_previous_ladder_snapshot",
    "save_ladder_snapshot",
    "today_trade_date_iso",
]

_LADDER_COLUMNS = (
    eld.c.trade_date,
    eld.c.max_limit_times,
    eld.c.max_board_vt_symbol,
    eld.c.linked_board_vt_symbols,
    eld.c.updated_at,
)


class EmotionLadderDailySnapshot(FrozenModel):
    trade_date: str = Field(description="交易日 YYYY-MM-DD")
    max_limit_times: int = Field(default=0, description="当日最高连板")
    max_board_vt_symbol: str = Field(default="", description="最高连板 vt_symbol")
    linked_board_vt_symbols: tuple[str, ...] = Field(default=(), description="≥2 板 vt_symbol 列表")
    board_counts: dict[str, int] = Field(default_factory=dict, description="vt_symbol → 连板数")
    updated_at: str = Field(default="", description="写入时间")


class EmotionLadderRepository(AppBaseRepository):
    table = eld

    def save(self, snapshot: EmotionLadderDailySnapshot) -> None:
        payload = json.dumps(list(snapshot.linked_board_vt_symbols), ensure_ascii=False)
        counts_payload = json.dumps(snapshot.board_counts, ensure_ascii=False)
        updated_at = snapshot.updated_at or format_china_datetime()
        trade_day = snapshot.trade_date[:10]

        def _write(conn) -> None:
            stmt = pg_insert(eld).values(
                trade_date=trade_day,
                max_limit_times=int(snapshot.max_limit_times),
                max_board_vt_symbol=snapshot.max_board_vt_symbol,
                linked_board_vt_symbols=payload,
                updated_at=updated_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[eld.c.trade_date],
                set_={
                    "max_limit_times": stmt.excluded.max_limit_times,
                    "max_board_vt_symbol": stmt.excluded.max_board_vt_symbol,
                    "linked_board_vt_symbols": stmt.excluded.linked_board_vt_symbols,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            conn.execute_stmt(stmt)
            meta_stmt = pg_insert(meta).values(
                key=f"emotion_ladder_counts:{trade_day}",
                value=counts_payload,
            )
            meta_stmt = meta_stmt.on_conflict_do_update(
                index_elements=[meta.c.key],
                set_={"value": meta_stmt.excluded.value},
            )
            conn.execute_stmt(meta_stmt)

        self.run(_write)

    def load(self, trade_date: str) -> EmotionLadderDailySnapshot | None:
        day = trade_date[:10]
        row = self.fetchone(select(*_LADDER_COLUMNS).where(eld.c.trade_date == day))
        if row is None:
            return None
        counts_raw = MetaRepository().get_value(f"emotion_ladder_counts:{day}")
        board_counts: dict[str, int] = {}
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


_repo = EmotionLadderRepository()


def today_trade_date_iso() -> str:
    return date.today().isoformat()


def save_ladder_snapshot(snapshot: EmotionLadderDailySnapshot) -> None:
    _repo.save(snapshot)


def load_ladder_snapshot(trade_date: str) -> EmotionLadderDailySnapshot | None:
    return _repo.load(trade_date)


def load_previous_ladder_snapshot(trade_date: str | None = None) -> EmotionLadderDailySnapshot | None:
    current = date.fromisoformat((trade_date or today_trade_date_iso())[:10])
    prev = previous_open_trading_day(current)
    if prev is None:
        return None
    return load_ladder_snapshot(prev.isoformat())
