"""Trace 持久化测试。"""

from __future__ import annotations

import os
import unittest

from vnpy_common.ai.protocol import AiChartBar, AiChartSpec
from vnpy_common.auth.context import clear_current_user, set_current_user
from vnpy_common.storage.config import force_database_url, reset_storage_config

from vnpy_ashare.storage.auth.users import get_or_create_default_user_id
from vnpy_ashare.storage.connection import init_app_db
from vnpy_llm.trace.persistence import TracePersistence
from vnpy_llm.trace.trace import TraceStore


class TracePersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            self.skipTest("需要 DATABASE_URL")
        reset_storage_config()
        force_database_url(url)
        init_app_db()
        set_current_user(get_or_create_default_user_id())
        self.persistence = TracePersistence()
        self.store = TraceStore(self.persistence)

    def tearDown(self) -> None:
        clear_current_user()
        reset_storage_config()

    def test_save_and_reload_turn(self) -> None:
        turn = self.store.start_turn("sess-1", "诊断 600519")
        self.store.add_chart_attachment(
            AiChartSpec(
                chart_id="c1",
                kind="candlestick",
                symbol="600519.SSE",
                series=[
                    AiChartBar(
                        date="2026-06-24",
                        open=1,
                        high=2,
                        low=0.5,
                        close=1.5,
                    )
                ],
            )
        )
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
        self.assertEqual(len(turns[0].attachments), 1)
        self.assertEqual(turns[0].attachments[0].symbol, "600519.SSE")
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
