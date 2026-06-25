"""个股分析报告 repository。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, insert, select
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.storage.tables import stock_analysis_reports as sar

REPORT_MAX_BODY = 128000
REPORT_MAX_TITLE = 200
SUMMARY_MAX = 240

_REPORT_COLUMNS = (
    sar.c.id,
    sar.c.symbol,
    sar.c.exchange,
    sar.c.title,
    sar.c.body,
    sar.c.source_scope,
    sar.c.context_json,
    sar.c.summary,
    sar.c.created_at,
    sar.c.updated_at,
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clip_text(text: str, max_len: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len]


def _build_summary(body: str) -> str:
    text_body = " ".join(line.strip() for line in body.strip().splitlines() if line.strip())
    if len(text_body) <= SUMMARY_MAX:
        return text_body
    return text_body[:SUMMARY_MAX] + "…"


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


class StockAnalysisReportRepository(AppUserScopedRepository):
    table = sar

    def _item_filter(self, symbol: str, exchange: Exchange):
        return (sar.c.symbol == symbol) & (sar.c.exchange == exchange.name)

    def create(
        self,
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

        def _write(conn):
            row = conn.execute_stmt(
                insert(sar)
                .values(
                    user_id=self.current_user_id(),
                    symbol=symbol,
                    exchange=exchange.name,
                    title=report_title,
                    body=report_body,
                    source_scope=scope,
                    context_json=context,
                    summary=summary,
                    created_at=now,
                    updated_at=now,
                )
                .returning(sar.c.id)
            ).fetchone()
            if row is None:
                raise RuntimeError("创建分析报告失败")
            return row

        row = self.run(_write)
        return {
            "id": int(row["id"]),
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

    def get(self, report_id: int) -> dict[str, str | int] | None:
        rows = self.fetchall(
            select(*_REPORT_COLUMNS).where(self.scope(sar.c.id == int(report_id))).limit(1)
        )
        return _row_to_dict(rows[0]) if rows else None

    def list_for_symbol(self, symbol: str, exchange: Exchange, *, limit: int = 100) -> list[dict[str, str | int]]:
        limit = max(1, min(int(limit), 500))
        rows = self.fetchall(
            select(*_REPORT_COLUMNS)
            .where(self.scope(self._item_filter(symbol, exchange)))
            .order_by(sar.c.created_at.desc(), sar.c.id.desc())
            .limit(limit)
        )
        return [_row_to_dict(row) for row in rows]

    def delete(self, report_id: int) -> bool:
        return self.delete_matching(self.scope(sar.c.id == int(report_id))) > 0

    def list_symbols(self) -> list[tuple[str, str]]:
        rows = self.fetchall(
            select(sar.c.symbol, sar.c.exchange)
            .where(self.scope())
            .group_by(sar.c.symbol, sar.c.exchange)
            .order_by(sar.c.symbol, sar.c.exchange)
        )
        return [(row["symbol"], row["exchange"]) for row in rows]


_repo = StockAnalysisReportRepository()


def create_report(
    symbol: str,
    exchange: Exchange,
    *,
    title: str,
    body: str,
    source_scope: str = "",
    context_json: str = "",
) -> dict[str, str | int]:
    return _repo.create(
        symbol,
        exchange,
        title=title,
        body=body,
        source_scope=source_scope,
        context_json=context_json,
    )


def get_report(report_id: int) -> dict[str, str | int] | None:
    return _repo.get(report_id)


def list_reports(symbol: str, exchange: Exchange, *, limit: int = 100) -> list[dict[str, str | int]]:
    return _repo.list_for_symbol(symbol, exchange, limit=limit)


def delete_report(report_id: int) -> bool:
    return _repo.delete(report_id)


def list_symbols_with_reports() -> list[tuple[str, str]]:
    return _repo.list_symbols()
