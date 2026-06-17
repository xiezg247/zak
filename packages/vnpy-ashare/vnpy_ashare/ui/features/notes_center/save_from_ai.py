"""从 AI 对话保存个股笔记。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from vnpy.trader.constant import Exchange
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.app.engine_access import get_note_service
from vnpy_ashare.domain.datetime import format_china_datetime_minute
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


def default_ai_report_title(stock: ContextStock, *, turn_count: int = 1) -> str:
    stamp = format_china_datetime_minute()
    head = stock.name or stock.symbol
    if turn_count <= 1:
        return f"{head} · AI 对话 · {stamp}"
    return f"{head} · AI 对话 {turn_count}轮 · {stamp}"


class _ChatMessageLike(Protocol):
    role: str
    content: str


def format_turn_exchange(user_text: str, assistant_text: str) -> str:
    """单轮问答格式化为 Markdown。"""
    parts: list[str] = []
    user = user_text.strip()
    assistant = assistant_text.strip()
    if user:
        parts.append(f"**问：** {user}")
    if assistant:
        parts.append(f"**答：**\n\n{assistant}")
    return "\n\n".join(parts)


def build_recent_turns_markdown(
    messages: Sequence[_ChatMessageLike],
    *,
    turn_count: int = 1,
) -> str:
    """取最近 N 轮（用户问 + 助手答）合并为 Markdown。"""
    limit = max(1, int(turn_count))
    turns: list[str] = []
    index = len(messages) - 1
    while index >= 0 and len(turns) < limit:
        msg = messages[index]
        if msg.role != "assistant" or not str(msg.content).strip():
            index -= 1
            continue
        assistant = str(msg.content).strip()
        user = ""
        probe = index - 1
        while probe >= 0:
            prior = messages[probe]
            if prior.role == "user":
                user = str(prior.content).strip()
                break
            if prior.role == "assistant":
                break
            probe -= 1
        block = format_turn_exchange(user, assistant)
        if block.strip():
            turns.append(block)
        index = probe - 1 if probe >= 0 else index - 1
    turns.reverse()
    return "\n\n---\n\n".join(turns)


def save_recent_turns_as_report(
    main_engine: MainEngine,
    messages: Sequence[_ChatMessageLike],
    *,
    turn_count: int = 1,
    parent: QtWidgets.QWidget | None = None,
    stock: ContextStock | None = None,
) -> bool:
    body = build_recent_turns_markdown(messages, turn_count=turn_count)
    if not body.strip():
        return False
    resolved = stock or resolve_context_stock()
    if resolved is None:
        return False
    title = default_ai_report_title(resolved, turn_count=turn_count)
    return save_message_as_report(
        main_engine,
        body,
        parent=parent,
        stock=resolved,
        default_title=title,
    )


def save_recent_turns_as_journal(
    main_engine: MainEngine,
    messages: Sequence[_ChatMessageLike],
    *,
    turn_count: int = 1,
    stock: ContextStock | None = None,
) -> bool:
    body = build_recent_turns_markdown(messages, turn_count=turn_count)
    if not body.strip():
        return False
    return save_message_as_journal(main_engine, body, stock=stock)


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
