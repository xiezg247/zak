"""内嵌 Trace 文案与配对测试。"""

import unittest

from vnpy_llm.chat.store import ChatMessage
from vnpy_llm.trace.trace import TraceStep, TurnTrace, map_turns_to_user_messages
from vnpy_llm.ui.trace.widgets import format_step_line, trace_header_text


class InlineTraceWidgetTest(unittest.TestCase):
    def test_trace_header_collapsed_summary(self) -> None:
        turn = TurnTrace(
            turn_id="t1",
            session_id="s1",
            user_text="hello",
            status="ok",
            steps=[
                TraceStep(
                    id="s1",
                    turn_id="t1",
                    kind="routing",
                    name="intent_route",
                    status="ok",
                    summary="quote · high",
                    detail={"category": "diagnosis"},
                ),
                TraceStep(
                    id="s2",
                    turn_id="t1",
                    kind="tool",
                    name="diagnose_stock",
                    status="ok",
                    summary="综合诊断",
                ),
            ],
        )
        header = trace_header_text(turn, expanded=False)
        self.assertTrue(header.startswith("▶"))
        self.assertIn("diagnosis", header)
        self.assertIn("综合诊断", header)
        self.assertIn("完成", header)

    def test_trace_header_with_handoff(self) -> None:
        turn = TurnTrace(
            turn_id="t1",
            session_id="s1",
            user_text="hello",
            status="ok",
            steps=[
                TraceStep(
                    id="s1",
                    turn_id="t1",
                    kind="routing",
                    name="intent_route",
                    status="ok",
                    summary="diagnosis → research",
                    detail={"category": "diagnosis", "target_agent": "research"},
                ),
                TraceStep(
                    id="s2",
                    turn_id="t1",
                    kind="handoff",
                    name="research->market",
                    status="ok",
                    summary="结合大盘情绪",
                    detail={"to_agent": "market"},
                ),
            ],
        )
        header = trace_header_text(turn, expanded=False)
        self.assertIn("diagnosis→research", header)
        self.assertIn("→market", header)

    def test_format_step_line(self) -> None:
        step = TraceStep(
            id="s2",
            turn_id="t1",
            kind="tool",
            name="diagnose_stock",
            status="ok",
            summary="综合诊断",
            duration_ms=128,
        )
        line = format_step_line(step, 2)
        self.assertIn("综合诊断", line)
        self.assertIn("128ms", line)


class MapTurnsToMessagesTest(unittest.TestCase):
    def test_align_latest_turn_to_latest_user(self) -> None:
        messages = [
            ChatMessage(role="user", content="旧问题"),
            ChatMessage(role="assistant", content="旧回答"),
            ChatMessage(role="user", content="新问题"),
            ChatMessage(role="assistant", content="新回答"),
        ]
        turns = [
            TurnTrace(
                turn_id="t-new",
                session_id="s1",
                user_text="新问题",
                status="ok",
            )
        ]
        mapping = map_turns_to_user_messages(messages, turns)
        self.assertEqual(mapping[2].turn_id, "t-new")
        self.assertNotIn(0, mapping)

    def test_match_by_user_text(self) -> None:
        messages = [
            ChatMessage(role="user", content="A"),
            ChatMessage(role="assistant", content="a"),
            ChatMessage(role="user", content="B"),
            ChatMessage(role="assistant", content="b"),
        ]
        turns = [
            TurnTrace(turn_id="t1", session_id="s1", user_text="A", status="ok"),
            TurnTrace(turn_id="t2", session_id="s1", user_text="B", status="ok"),
        ]
        mapping = map_turns_to_user_messages(messages, turns)
        self.assertEqual(mapping[0].turn_id, "t1")
        self.assertEqual(mapping[2].turn_id, "t2")


if __name__ == "__main__":
    unittest.main()
