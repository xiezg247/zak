"""从 AI 对话保存个股笔记。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vnpy.trader.constant import Exchange
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.app.engine_access import get_note_service
from vnpy_ashare.services.note_service import build_report_context_json
from vnpy_ashare.ui.features.stock_analysis.save_report_dialog import SaveAnalysisReportDialog
from vnpy_common.ai.access import get_ai_context


@dataclass(frozen=True)
class ContextStock:
    symbol: str
    exchange: str
    name: str

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


def resolve_context_stock() -> ContextStock | None:
    data = get_ai_context()
    symbol = str(data.symbol or "").strip()
    exchange = str(data.exchange or "").strip()
    if not symbol or not exchange:
        return None
    if exchange not in Exchange.__members__:
        return None
    return ContextStock(symbol=symbol, exchange=exchange, name=str(data.name or "").strip())


def default_ai_report_title(stock: ContextStock) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    head = stock.name or stock.symbol
    return f"{head} · AI 对话 · {stamp}"


def save_message_as_report(
    main_engine: MainEngine,
    body: str,
    *,
    parent: QtWidgets.QWidget | None = None,
    stock: ContextStock | None = None,
    default_title: str = "",
) -> bool:
    text = body.strip()
    if not text:
        return False
    resolved = stock or resolve_context_stock()
    if resolved is None:
        return False
    service = get_note_service(main_engine)
    if service is None:
        return False
    title = default_title.strip() or default_ai_report_title(resolved)
    dialog = SaveAnalysisReportDialog(
        default_title=title,
        default_body=text,
        parent=parent,
    )
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return False
    final_body = dialog.body_text()
    if not final_body:
        return False
    context_json = build_report_context_json(scope="ai_chat", summary=f"页面：{get_ai_context().page}")
    service.create_report(
        resolved.symbol,
        Exchange[resolved.exchange],
        title=dialog.title_text() or title,
        body=final_body,
        source_scope="ai_chat",
        context_json=context_json,
    )
    return True


def save_message_as_journal(
    main_engine: MainEngine,
    body: str,
    *,
    stock: ContextStock | None = None,
) -> bool:
    text = body.strip()
    if not text:
        return False
    resolved = stock or resolve_context_stock()
    if resolved is None:
        return False
    service = get_note_service(main_engine)
    if service is None:
        return False
    entry = service.append_entry(resolved.symbol, Exchange[resolved.exchange], text)
    return entry is not None
