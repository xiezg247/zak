"""HITL 草案 pending_confirm 测试。"""

from __future__ import annotations

from vnpy_llm.graph.hitl import (
    DraftPendingStop,
    HITL_HINTS,
    parse_draft_pending,
)
from vnpy_llm.graph.runner import _wrap_tool_executor


def test_parse_draft_pending_recipe():
    payload = '{"status":"pending_confirm","draft_id":"abc123","summary":"盘中多因子 Top 20"}'
    info = parse_draft_pending("propose_recipe", payload)
    assert info is not None
    assert info.draft_id == "abc123"
    assert info.draft_kind == "recipe"
    assert info.summary == "盘中多因子 Top 20"


def test_parse_draft_pending_ignores_direct_run():
    assert parse_draft_pending("run_recipe", '{"status":"ok","count":3}') is None


def test_wrap_tool_executor_raises_on_draft_pending():
    pending_calls: list[str] = []

    def executor(name: str, arguments: dict) -> str:
        return (
            '{"status":"pending_confirm","draft_id":"d1",'
            '"summary":"盘后多因子","message":"待确认"}'
        )

    def on_draft(info) -> None:
        pending_calls.append(info.draft_id)

    wrapped = _wrap_tool_executor(executor, on_draft)
    try:
        wrapped("propose_recipe", {"intent": "复杂多因子"})
        raise AssertionError("expected DraftPendingStop")
    except DraftPendingStop as ex:
        assert ex.info.draft_id == "d1"
    assert pending_calls == ["d1"]
