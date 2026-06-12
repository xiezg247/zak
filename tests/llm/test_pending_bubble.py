"""进行中占位气泡文案测试。"""

from __future__ import annotations

import unittest

from vnpy_llm.trace.trace import TraceStep, TurnTrace
from vnpy_llm.ui.panel.pending_bubble import format_pending_html, pending_status_from_turn


def _turn(*steps: TraceStep) -> TurnTrace:
    return TurnTrace(
        turn_id="t1",
        session_id="s1",
        user_text="测试",
        steps=list(steps),
    )


def _step(*, kind: str, name: str, status: str = "running", summary: str = "") -> TraceStep:
    return TraceStep(
        id="x",
        turn_id="t1",
        kind=kind,  # type: ignore[arg-type]
        name=name,
        status=status,  # type: ignore[arg-type]
        summary=summary,
    )


class PendingBubbleTests(unittest.TestCase):
    def test_default_thinking(self) -> None:
        main, sub = pending_status_from_turn(None)
        self.assertEqual(main, "思考中…")
        self.assertIn("收到", sub)

    def test_tool_running(self) -> None:
        turn = _turn(_step(kind="tool", name="diagnose_stock"))
        main, sub = pending_status_from_turn(turn)
        self.assertIn("综合诊断", main)
        self.assertIn("稍候", sub)

    def test_parallel_tools(self) -> None:
        turn = _turn(
            _step(kind="tool", name="get_bars_summary"),
            _step(kind="tool", name="diagnose_stock"),
        )
        main, _ = pending_status_from_turn(turn)
        self.assertIn("并行", main)

    def test_reply_running(self) -> None:
        turn = _turn(
            _step(kind="tool", name="diagnose_stock", status="ok"),
            _step(kind="reply", name="assistant_reply"),
        )
        main, sub = pending_status_from_turn(turn)
        self.assertIn("整理", main)
        self.assertIn("回复", sub)

    def test_after_routing(self) -> None:
        turn = _turn(_step(kind="routing", name="intent_route", status="ok"))
        main, _ = pending_status_from_turn(turn)
        self.assertIn("准备查询", main)

    def test_hitl_waiting(self) -> None:
        turn = _turn(
            _step(
                kind="hitl",
                name="draft_screener",
                status="ok",
                summary="涨幅榜 Top 20",
            ),
        )
        main, sub = pending_status_from_turn(turn)
        self.assertIn("确认", main)
        self.assertIn("涨幅榜", sub)

    def test_handoff_switch(self) -> None:
        turn = _turn(
            _step(kind="handoff", name="research->market", status="ok", summary="结合大盘情绪"),
        )
        turn.steps[0].detail = {"to_agent": "market"}
        main, sub = pending_status_from_turn(turn)
        self.assertIn("market", main)
        self.assertIn("大盘", sub)

    def test_format_html(self) -> None:
        html = format_pending_html("思考中…", "请稍候", spinner="●")
        self.assertIn("●", html)
        self.assertIn("思考中", html)
        self.assertIn("请稍候", html)


if __name__ == "__main__":
    unittest.main()
