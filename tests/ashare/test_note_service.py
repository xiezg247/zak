"""个股笔记 Service 测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.stock_note import StockNoteBundle
from vnpy_ashare.services.note import NoteService
from vnpy_ashare.storage.connection import init_app_db


class NoteServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()
        engine = Mock()
        engine.main_engine = None
        engine.event_engine = None
        self.service = NoteService(engine)

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_build_ai_snippet_with_memo_and_entries(self) -> None:
        self.service.upsert_memo("600519", Exchange.SSE, "长期持有逻辑")
        self.service.append_entry("600519", Exchange.SSE, "突破均线")
        bundle = self.service.get_bundle("600519", Exchange.SSE)
        snippet = self.service.build_ai_snippet(bundle)
        self.assertIn("【备忘】", snippet)
        self.assertIn("长期持有逻辑", snippet)
        self.assertIn("【最近流水】", snippet)
        self.assertIn("突破均线", snippet)

    def test_build_ai_snippet_empty(self) -> None:
        bundle = StockNoteBundle(
            symbol="600519",
            exchange=Exchange.SSE.name,
            memo=None,
            entries=[],
        )
        self.assertEqual(self.service.build_ai_snippet(bundle), "")

    def test_build_ai_snippet_with_reports(self) -> None:
        self.service.create_report(
            "600519",
            Exchange.SSE,
            title="概览解读",
            body="长期看好",
            source_scope="overview",
        )
        bundle = self.service.get_bundle("600519", Exchange.SSE)
        snippet = self.service.build_ai_snippet(bundle)
        self.assertIn("【分析报告】", snippet)
        self.assertIn("概览解读", snippet)

    def test_export_markdown(self) -> None:
        self.service.upsert_memo("600519", Exchange.SSE, "逻辑")
        self.service.append_entry("600519", Exchange.SSE, "观察")
        self.service.create_report(
            "600519",
            Exchange.SSE,
            title="AI 解读",
            body="## 结论\n看好",
            source_scope="overview",
        )
        bundle = self.service.get_bundle("600519", Exchange.SSE)
        text = self.service.format_markdown(bundle, name="贵州茅台")
        self.assertIn("600519.SSE", text)
        self.assertIn("## 备忘", text)
        self.assertIn("## 流水", text)
        self.assertIn("## 分析报告", text)
        self.assertIn("看好", text)


if __name__ == "__main__":
    unittest.main()
