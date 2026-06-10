"""TraceStore 单元测试。"""

import unittest

from vnpy_llm.trace.trace import TraceStore, preview_text


class TraceStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = TraceStore()

    def test_turn_and_tool_steps(self) -> None:
        turn = self.store.start_turn("sess-1", "诊断 600519")
        self.assertEqual(turn.session_id, "sess-1")
        self.assertIs(self.store.current_turn(), turn)

        route = self.store.add_step(
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
        finished = self.store.finish_turn("ok")
        assert finished is not None
        self.assertEqual(finished.status, "ok")
        self.assertEqual(len(finished.steps), 2)
        self.assertIsNone(self.store.current_turn())

        turns = self.store.list_turns("sess-1")
        self.assertEqual(len(turns), 1)
        self.assertIsNotNone(turns[0].steps[1].duration_ms)

    def test_clear_session(self) -> None:
        self.store.start_turn("sess-a", "hello")
        self.store.start_turn("sess-b", "world")
        self.store.clear_session("sess-a")
        self.assertEqual(self.store.list_turns("sess-a"), [])
        self.assertEqual(len(self.store.list_turns("sess-b")), 1)

    def test_preview_text(self) -> None:
        long_text = "x" * 700
        preview = preview_text(long_text, limit=600)
        self.assertTrue(preview.endswith("…"))
        self.assertLessEqual(len(preview), 601)


if __name__ == "__main__":
    unittest.main()
