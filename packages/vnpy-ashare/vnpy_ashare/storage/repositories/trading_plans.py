"""交易计划 repository（J-01）。"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.trading.plan import TradingPlanRecord, TradingPlanSymbolRecord
from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_common.auth.scope import user_sql

PLAN_MAX_SYMBOLS = 5

PlanSymbolRow = tuple[str, Exchange] | tuple[str, Exchange, tuple[str, ...] | None]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_modes(text: str) -> tuple[str, ...]:
    parts = [item.strip() for item in str(text or "").split(",") if item.strip()]
    return tuple(parts)


def _modes_to_text(modes: tuple[str, ...] | list[str]) -> str:
    return ",".join(item.strip() for item in modes if item.strip())


def _row_to_symbol(row, *, sort_order: int) -> TradingPlanSymbolRecord:
    return TradingPlanSymbolRecord(
        symbol=str(row["symbol"]),
        exchange=str(row["exchange"]),
        allowed_modes=_parse_modes(row["allowed_modes"]),
        entry_conditions=str(row["entry_conditions"] or ""),
        exit_conditions=str(row["exit_conditions"] or ""),
        sort_order=int(row["sort_order"]) if "sort_order" in row.keys() else sort_order,
    )


def _load_plan_symbols(conn, plan_id: str, uid: str) -> tuple[TradingPlanSymbolRecord, ...]:
    rows = conn.execute(
        f"""
        SELECT symbol, exchange, allowed_modes, entry_conditions, exit_conditions, sort_order
        FROM trading_plan_symbols
        WHERE {user_sql('plan_id = ?')}
        ORDER BY sort_order, symbol
        """,
        (uid, plan_id),
    ).fetchall()
    return tuple(_row_to_symbol(row, sort_order=index) for index, row in enumerate(rows))


def _batch_load_symbols(conn, plan_ids: list[str], uid: str) -> dict[str, tuple[TradingPlanSymbolRecord, ...]]:
    """批量加载所有计划标的（一次查询代替 N 次）。"""
    if not plan_ids:
        return {}
    placeholders = ",".join("?" for _ in plan_ids)
    rows = conn.execute(
        f"""
        SELECT plan_id, symbol, exchange, allowed_modes, entry_conditions, exit_conditions, sort_order
        FROM trading_plan_symbols
        WHERE {user_sql(f'plan_id IN ({placeholders})')}
        ORDER BY plan_id, sort_order, symbol
        """,
        (uid, *plan_ids),
    ).fetchall()
    by_plan: dict[str, list[TradingPlanSymbolRecord]] = {}
    for row in rows:
        pid = str(row["plan_id"])
        by_plan.setdefault(pid, []).append(_row_to_symbol(row, sort_order=len(by_plan[pid])))
    return {pid: tuple(items) for pid, items in by_plan.items()}


def _row_to_plan(row, symbols: tuple[TradingPlanSymbolRecord, ...]) -> TradingPlanRecord:
    return TradingPlanRecord(
        id=str(row["id"]),
        trade_date=str(row["trade_date"]),
        emotion_expected=str(row["emotion_expected"] or ""),
        max_position_pct=float(row["max_position_pct"] or 0),
        notes=str(row["notes"] or ""),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        symbols=symbols,
    )


def load_trading_plan(plan_id: str) -> TradingPlanRecord | None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(f"SELECT * FROM trading_plans WHERE {user_sql('id = ?')}", (uid, plan_id)).fetchone()
        if row is None:
            return None
        symbols = _load_plan_symbols(conn, plan_id, uid)
        return _row_to_plan(row, symbols)


def load_active_trading_plan(trade_date: str) -> TradingPlanRecord | None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM trading_plans
            WHERE {user_sql("trade_date = ? AND status = 'active'")}
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (uid, trade_date[:10]),
        ).fetchone()
        if row is None:
            return None
        symbols = _load_plan_symbols(conn, str(row["id"]), uid)
        return _row_to_plan(row, symbols)


def list_trading_plans(*, limit: int = 20) -> list[TradingPlanRecord]:
    """列出交易计划 —— 批量加载标的避免 N+1。"""
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM trading_plans WHERE {user_sql()} ORDER BY trade_date DESC, updated_at DESC LIMIT ?",
            (uid, max(1, limit)),
        ).fetchall()
        if not rows:
            return []
        plan_ids = [str(row["id"]) for row in rows]
        symbols_map = _batch_load_symbols(conn, plan_ids, uid)
        return [_row_to_plan(row, symbols_map.get(str(row["id"]), ())) for row in rows]


def create_trading_plan(
    *,
    trade_date: str,
    emotion_expected: str = "",
    max_position_pct: float = 0.0,
    notes: str = "",
    status: str = "draft",
    symbols: list[tuple[str, Exchange]] | None = None,
) -> str | None:
    normalized_date = trade_date[:10]
    if not normalized_date:
        return None
    plan_id = uuid.uuid4().hex
    now = _now_iso()
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO trading_plans(
                id, user_id, trade_date, emotion_expected, max_position_pct, notes, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id, uid, normalized_date, emotion_expected.strip(),
                max(0.0, min(float(max_position_pct), 1.0)), notes.strip(),
                status, now, now,
            ),
        )
        if symbols:
            _replace_plan_symbols_conn(conn, uid, plan_id, symbols)
    return plan_id


def update_trading_plan_meta(
    plan_id: str,
    *,
    emotion_expected: str | None = None,
    max_position_pct: float | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> bool:
    init_app_db()
    fields: list[str] = []
    values: list[object] = []
    if emotion_expected is not None:
        fields.append("emotion_expected = ?")
        values.append(emotion_expected.strip())
    if max_position_pct is not None:
        fields.append("max_position_pct = ?")
        values.append(max(0.0, min(float(max_position_pct), 1.0)))
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes.strip())
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if not fields:
        return False
    fields.append("updated_at = ?")
    values.append(_now_iso())
    uid = get_user_id()
    values.extend([uid, plan_id])
    with connect() as conn:
        cursor = conn.execute(
            f"UPDATE trading_plans SET {', '.join(fields)} WHERE {user_sql('id = ?')}",
            tuple(values),
        )
        return bool(cursor.rowcount > 0)


def _replace_plan_symbols_conn(
    conn,
    uid: str,
    plan_id: str,
    symbols: Sequence[PlanSymbolRow],
) -> None:
    conn.execute(f"DELETE FROM trading_plan_symbols WHERE {user_sql('plan_id = ?')}", (uid, plan_id))
    if not symbols:
        return
    batch = []
    for index, item in enumerate(symbols[:PLAN_MAX_SYMBOLS]):
        if len(item) == 2:
            symbol, exchange = item
            modes: tuple[str, ...] = ()
        else:
            symbol, exchange, modes_raw = item
            modes = tuple(modes_raw) if modes_raw else ()
        batch.append((
            uid, plan_id, symbol, exchange.name,
            _modes_to_text(modes or ()), "", "", index,
        ))
    conn.executemany(
        """
        INSERT INTO trading_plan_symbols(
            user_id, plan_id, symbol, exchange, allowed_modes, entry_conditions, exit_conditions, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )


def replace_trading_plan_symbols(
    plan_id: str,
    symbols: list[tuple[str, Exchange]],
) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        exists = conn.execute(f"SELECT 1 FROM trading_plans WHERE {user_sql('id = ?')}", (uid, plan_id)).fetchone()
        if exists is None:
            return False
        _replace_plan_symbols_conn(
            conn, uid, plan_id,
            [(symbol, exchange) for symbol, exchange in symbols[:PLAN_MAX_SYMBOLS]],
        )
    return True


def activate_trading_plan(plan_id: str) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(f"SELECT trade_date FROM trading_plans WHERE {user_sql('id = ?')}", (uid, plan_id)).fetchone()
        if row is None:
            return False
        trade_date = str(row["trade_date"])
        conn.execute(
            f"UPDATE trading_plans SET status = 'archived', updated_at = ? WHERE {user_sql("trade_date = ? AND status = 'active'")}",
            (_now_iso(), uid, trade_date),
        )
        cursor = conn.execute(
            f"UPDATE trading_plans SET status = 'active', updated_at = ? WHERE {user_sql('id = ?')}",
            (_now_iso(), uid, plan_id),
        )
        return bool(cursor.rowcount > 0)
