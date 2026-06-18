"""从笔记流水导入 trade_journal。"""

from __future__ import annotations

from vnpy_ashare.domain.models.stock_note import StockNoteEntry
from vnpy_ashare.storage.repositories.stock_notes import get_entry as get_stock_note_entry
from vnpy_ashare.storage.repositories.trade_journal import insert_trade_journal_entry


def _trade_date_from_created_at(created_at: str) -> str:
    text = str(created_at or "").strip()
    if not text:
        return ""
    if "T" in text:
        return text.split("T", 1)[0]
    if " " in text:
        return text.split(" ", 1)[0]
    return text[:10]


def import_stock_note_entry(entry: StockNoteEntry) -> int | None:
    """将笔记流水写入 trade_journal（side=hold，reason=正文）。"""
    trade_date = _trade_date_from_created_at(entry.created_at)
    if not trade_date:
        return None
    body = str(entry.body or "").strip()
    if not body:
        return None
    reason = body if len(body) <= 500 else body[:497] + "..."
    return insert_trade_journal_entry(
        symbol=entry.symbol,
        exchange=entry.exchange,
        side="hold",
        trade_date=trade_date,
        price=0.0,
        volume=1,
        mode="other",
        on_plan=True,
        reason=f"[笔记导入] {reason}",
    )


def import_stock_note_by_id(entry_id: int) -> int | None:
    row = get_stock_note_entry(entry_id)
    if row is None:
        return None
    entry = StockNoteEntry(
        id=int(row["id"]),
        symbol=str(row["symbol"]),
        exchange=str(row["exchange"]),
        body=str(row["body"]),
        created_at=str(row["created_at"]),
    )
    return import_stock_note_entry(entry)
