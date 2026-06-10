"""Trace 持久化测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_llm.chat import store
from vnpy_llm.trace.trace import TraceStore
from vnpy_llm.trace.persistence import TracePersistence


class TracePersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch.object(store, "_chat_db_path", return_value=self.db_path)
        self._patcher.start()
        self.persistence = TracePersistence()
        self.store = TraceStore(self.persistence)

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_save_and_reload_turn(self) -> None:
        turn = self.store.start_turn("sess-1", "诊断 600519")
        self.store.add_step(
            kind="routing",
            name="intent_route",
            summary="diagnosis · high",
            status="ok",
        )
        tool = self.store.add_step(
            kind="tool",
            name="diagnose_stock",
            summary="综合诊断…",
            detail={"arguments": {"symbol": "600519"}},
        )
        self.store.update_step(
            tool.id,
            status="ok",
            summary="综合诊断",
            detail={"result_preview": '{"score": 80}'},
        )
        self.store.finish_turn("ok")

        reloaded = TraceStore(self.persistence)
        reloaded.ensure_session_loaded("sess-1")
        turns = reloaded.list_turns("sess-1")
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].user_text, "诊断 600519")
        self.assertEqual(len(turns[0].steps), 2)
        self.assertEqual(turns[0].steps[1].name, "diagnose_stock")
        self.assertTrue(turns[0].created_at)

    def test_clear_session_removes_db_rows(self) -> None:
        self.store.start_turn("sess-1", "hello")
        self.store.finish_turn("ok")
        self.store.clear_session("sess-1")

        reloaded = TraceStore(self.persistence)
        reloaded.ensure_session_loaded("sess-1")
        self.assertEqual(reloaded.list_turns("sess-1"), [])

    def test_repair_interrupted_running_turn(self) -> None:
        turn = self.store.start_turn("sess-2", "进行中")
        self.store.add_step(
            kind="tool",
            name="get_watchlist",
            summary="查询自选池…",
        )
        self.persistence.save_turn(self.store.current_turn(), turn_index=0)

        reloaded = TraceStore(self.persistence)
        reloaded.ensure_session_loaded("sess-2")
        turns = reloaded.list_turns("sess-2")
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].status, "error")
        self.assertEqual(turns[0].steps[0].status, "error")


if __name__ == "__main__":
    unittest.main()
