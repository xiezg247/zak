"""从 AI 对话保存笔记测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401
from vnpy_ashare.services.note import NoteService
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.ui.features.notes_center.save_from_ai import (
    ContextStock,
    build_recent_turns_markdown,
    resolve_context_stock,
    save_message_as_journal,
    save_recent_turns_as_report,
)
from vnpy_common.ai.protocol import AiContextData
from vnpy_llm.chat.store import ChatMessage


class SaveFromAiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()
        engine = Mock()
        engine.main_engine = None
        engine.event_engine = None
        self.note_service = NoteService(engine)
        self.main_engine = Mock()
        self.main_engine.get_engine = Mock(return_value=Mock(note_service=self.note_service))

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_resolve_context_stock(self) -> None:
        with patch(
            "vnpy_ashare.ui.features.notes_center.save_from_ai.get_ai_context",
            return_value=AiContextData(page="自选", symbol="600519", exchange="SSE", name="茅台"),
        ):
            stock = resolve_context_stock()
        self.assertIsNotNone(stock)
        assert stock is not None
        self.assertEqual(stock.vt_symbol, "600519.SSE")

    def test_resolve_context_stock_cn_exchange(self) -> None:
        with patch(
            "vnpy_ashare.ui.features.notes_center.save_from_ai.get_ai_context",
            return_value=AiContextData(page="自选", symbol="600519", exchange="上交所", name="茅台"),
        ):
            stock = resolve_context_stock()
        self.assertIsNotNone(stock)
        assert stock is not None
        self.assertEqual(stock.vt_symbol, "600519.SSE")

    def test_save_journal(self) -> None:
        stock = ContextStock(symbol="600519", exchange="SSE", name="茅台")
        with patch(
            "vnpy_ashare.ui.features.notes_center.save_from_ai.get_note_service",
            return_value=self.note_service,
        ):
            ok = save_message_as_journal(self.main_engine, "AI 观点：观望", stock=stock)
        self.assertTrue(ok)
        bundle = self.note_service.get_bundle("600519", Exchange.SSE)
        self.assertEqual(len(bundle.entries), 1)

    def test_build_recent_turns_markdown_single(self) -> None:
        messages = [
            ChatMessage(role="user", content="这只票怎么样？"),
            ChatMessage(role="assistant", content="观望为主。"),
        ]
        text = build_recent_turns_markdown(messages, turn_count=1)
        self.assertIn("**问：**", text)
        self.assertIn("这只票怎么样？", text)
        self.assertIn("观望为主。", text)

    def test_build_recent_turns_markdown_multiple(self) -> None:
        messages = [
            ChatMessage(role="user", content="Q1"),
            ChatMessage(role="assistant", content="A1"),
            ChatMessage(role="user", content="Q2"),
            ChatMessage(role="assistant", content="A2"),
        ]
        text = build_recent_turns_markdown(messages, turn_count=2)
        self.assertIn("Q1", text)
        self.assertIn("A2", text)
        self.assertIn("---", text)

    def test_save_recent_turns_as_report(self) -> None:
        stock = ContextStock(symbol="600519", exchange="SSE", name="茅台")
        messages = [
            ChatMessage(role="user", content="团队分析"),
            ChatMessage(role="assistant", content="综合研判：中性。"),
        ]
        with (
            patch(
                "vnpy_ashare.ui.features.notes_center.save_from_ai.get_note_service",
                return_value=self.note_service,
            ),
            patch(
                "vnpy_ashare.ui.features.notes_center.save_from_ai.SaveAnalysisReportDialog",
            ) as dialog_cls,
        ):
            dialog = MagicMock()
            dialog.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
            dialog.title_text.return_value = "测试标题"
            dialog.body_text.return_value = "综合研判：中性。"
            dialog_cls.return_value = dialog
            ok = save_recent_turns_as_report(
                self.main_engine,
                messages,
                turn_count=1,
                stock=stock,
            )
        self.assertTrue(ok)
        reports = self.note_service.list_reports("600519", Exchange.SSE)
        self.assertEqual(len(reports), 1)
        self.assertIn("综合研判", reports[0].body)


if __name__ == "__main__":
    unittest.main()
