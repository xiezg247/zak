"""从 AI 对话保存笔记测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.services.note_service import NoteService
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.ui.features.notes_center.save_from_ai import (
    ContextStock,
    resolve_context_stock,
    save_message_as_journal,
)
from vnpy_common.ai.protocol import AiContextData


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


if __name__ == "__main__":
    unittest.main()
