"""笔记 AI 整理 / 扩写（单次 LLM 调用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore

from vnpy_ashare.ai.context.quote.format import format_quote_snapshot_line
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes.core.provider import resolve_quote_snapshot
from vnpy_llm.chat.client import LlmClientError, complete_chat_completion
from vnpy_llm.config.settings import LlmConfig

try:
    from vnpy_llm.app.engine import APP_NAME, LlmEngine
except ImportError:
    APP_NAME = ""
    LlmEngine = None  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class NoteAiWorker(QtCore.QThread):
    finished_ok = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        config: LlmConfig,
        messages: list[dict[str, str]],
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._messages = messages

    def run(self) -> None:
        try:
            text = complete_chat_completion(self._config, self._messages, max_tokens=1200)
            if not self.isInterruptionRequested():
                self.finished_ok.emit(text.strip())
        except LlmClientError as ex:
            if not self.isInterruptionRequested():
                self.failed.emit(str(ex))
        except Exception as ex:
            if not self.isInterruptionRequested():
                self.failed.emit(str(ex))


def get_llm_config(main_engine: MainEngine | None) -> LlmConfig | None:
    if main_engine is None or LlmEngine is None:
        return None
    engine = main_engine.get_engine(APP_NAME)
    if not isinstance(engine, LlmEngine):
        return None
    config = engine.config
    if not config.configured:
        return None
    return config


def build_quote_snapshot_line(page: QuotesPage, item: StockItem) -> str:
    quote = page.quote_map.get(item.tickflow_symbol)
    if quote is None:
        return ""
    return format_quote_snapshot_line(quote)


def build_quote_snapshot_for_item(item: StockItem) -> str:
    quote = resolve_quote_snapshot(item)
    if quote is None:
        return ""
    return format_quote_snapshot_line(quote)


def build_journal_polish_messages(
    raw_text: str,
    *,
    vt_symbol: str,
    name: str,
    quote_line: str = "",
) -> list[dict[str, str]]:
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    context = quote_line.strip() or "（无实时行情）"
    return [
        {
            "role": "system",
            "content": (
                "你是 A 股投研笔记助手。将用户的碎片观察整理成一条简洁流水记录。"
                "要求：纯文本一两句话；保留原意；删除口语废话；不编造数据；不构成买卖建议。"
                "只输出流水正文，不要标题、不要列表、不要 Markdown 代码块。"
            ),
        },
        {
            "role": "user",
            "content": f"标的：{title}\n行情：{context}\n观察：{raw_text.strip()}",
        },
    ]


def build_memo_expand_messages(
    full_memo: str,
    selection: str,
    *,
    vt_symbol: str,
    name: str,
) -> list[dict[str, str]]:
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    target = selection.strip() or full_memo.strip()
    if not target:
        raise ValueError("备忘内容为空")
    scope = "选中段落" if selection.strip() else "全文"
    return [
        {
            "role": "system",
            "content": (
                "你是 A 股投研笔记助手。扩写用户的备忘内容（Markdown）。"
                "要求：补充逻辑与要点；风格与原文一致；不编造行情或财务数据；不构成买卖建议。"
                f"只输出扩写后的{scope}正文，不要用代码块包裹，不要加「扩写如下」等前缀。"
            ),
        },
        {
            "role": "user",
            "content": (f"标的：{title}\n备忘全文：\n{full_memo.strip()}\n\n待扩写{scope}：\n{target}"),
        },
    ]


def apply_expanded_memo(full_text: str, selection: str, expanded: str) -> str:
    if selection.strip():
        cursor_start = full_text.find(selection)
        if cursor_start >= 0:
            return full_text[:cursor_start] + expanded + full_text[cursor_start + len(selection) :]
        return expanded
    return expanded
