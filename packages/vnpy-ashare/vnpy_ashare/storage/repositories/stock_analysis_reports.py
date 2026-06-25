"""个股分析报告 repository。"""

from __future__ import annotations

import json
from datetime import datetime

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_common.auth.scope import user_sql

REPORT_MAX_BODY = 128000
REPORT_MAX_TITLE = 200
SUMMARY_MAX = 240


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clip_text(text: str, max_len: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len]


def _build_summary(body: str) -> str:
    text = " ".join(line.strip() for line in body.strip().splitlines() if line.strip())
    if len(text) <= SUMMARY_MAX:
        return text
    return text[:SUMMARY_MAX] + "…"


def create_report(
    symbol: str,
    exchange: Exchange,
    *,
    title: str,
    body: str,
    source_scope: str = "",
    context_json: str = "",
) -> dict[str, str | int]:
    report_body = _clip_text(body, REPORT_MAX_BODY)
    if not report_body:
        raise ValueError("报告正文不能为空")
    report_title = _clip_text(title, REPORT_MAX_TITLE) or "分析报告"
    scope = _clip_text(source_scope, 32)
    context = context_json.strip()
    if context:
        try:
            json.loads(context)
        except json.JSONDecodeError:
            context = json.dumps({"text": context}, ensure_ascii=False)
    now = _now_iso()
    summary = _build_summary(report_body)
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO stock_analysis_reports(
                user_id, symbol, exchange, title, body, source_scope, context_json,
                summary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                uid,
                symbol,
                exchange.name,
                report_title,
                report_body,
                scope,
                context,
                summary,
                now,
                now,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("创建分析报告失败")
        report_id = int(row["id"])
    return {
        "id": report_id,
        "symbol": symbol,
        "exchange": exchange.name,
        "title": report_title,
        "body": report_body,
        "source_scope": scope,
        "context_json": context,
        "summary": summary,
        "created_at": now,
        "updated_at": now,
    }


def get_report(report_id: int) -> dict[str, str | int] | None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT id, symbol, exchange, title, body, source_scope, context_json,
                   summary, created_at, updated_at
            FROM stock_analysis_reports WHERE {user_sql('id = ?')}
            """,
            (uid, int(report_id),),
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_reports(
    symbol: str,
    exchange: Exchange,
    *,
    limit: int = 100,
) -> list[dict[str, str | int]]:
    limit = max(1, min(int(limit), 500))
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, symbol, exchange, title, body, source_scope, context_json,
                   summary, created_at, updated_at
            FROM stock_analysis_reports
            WHERE {user_sql('symbol = ? AND exchange = ?')}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (uid, symbol, exchange.name, limit),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_report(report_id: int) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        cursor = conn.execute(
            f"DELETE FROM stock_analysis_reports WHERE {user_sql('id = ?')}",
            (uid, int(report_id),),
        )
    return bool(cursor.rowcount > 0)


def list_symbols_with_reports() -> list[tuple[str, str]]:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT symbol, exchange FROM stock_analysis_reports
            WHERE {user_sql()}
            GROUP BY symbol, exchange
            ORDER BY symbol, exchange
            """,
            (uid,),
        ).fetchall()
    return [(row["symbol"], row["exchange"]) for row in rows]


def _row_to_dict(row) -> dict[str, str | int]:
    return {
        "id": int(row["id"]),
        "symbol": row["symbol"],
        "exchange": row["exchange"],
        "title": row["title"] or "",
        "body": row["body"] or "",
        "source_scope": row["source_scope"] or "",
        "context_json": row["context_json"] or "",
        "summary": row["summary"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
