"""nl_mapper 单元测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.nl_mapper import (
    ProposeInput,
    clamp_top_n,
    try_fast_path,
    validate_and_build,
)
from vnpy_ashare.screener.presets import SCREENER_CHANGE_TOP, SCREENER_CUSTOM, SCREENER_LOW_PE


def test_clamp_top_n():
    assert clamp_top_n(None) == 20
    assert clamp_top_n(0) == 1
    assert clamp_top_n(500) == 200


def test_fast_path_custom_filters():
    fast = try_fast_path("找涨幅超过5%、换手大于3%的前30只")
    assert fast is not None
    assert fast.preset == SCREENER_CUSTOM
    assert fast.min_change_pct == 5
    assert fast.min_turnover == 3
    assert fast.top_n == 30


def test_fast_path_low_pe():
    fast = try_fast_path("帮我筛低PE的大票")
    assert fast is not None
    assert fast.preset == SCREENER_LOW_PE


@patch("vnpy_ashare.screener.nl_mapper.collect_warnings", return_value=[])
def test_validate_builtin_preset(_mock_warnings):
    result = validate_and_build(ProposeInput(intent="今天涨最多的", preset=SCREENER_CHANGE_TOP, top_n=10, confidence="high"))
    assert result.kind == "pending_confirm"
    assert result.draft is not None
    assert result.draft.request.preset == SCREENER_CHANGE_TOP
    assert result.draft.request.top_n == 10


@patch("vnpy_ashare.screener.nl_mapper.collect_warnings", return_value=[])
def test_validate_custom_preset(_mock_warnings):
    result = validate_and_build(
        ProposeInput(
            intent="涨幅5%以上换手3%",
            preset=SCREENER_CUSTOM,
            top_n=20,
            min_change_pct=5,
            min_turnover=3,
            confidence="high",
        )
    )
    assert result.kind == "pending_confirm"
    assert result.draft is not None
    assert "涨幅 ≥5%" in result.draft.summary
    assert "换手 ≥3%" in result.draft.summary


def test_low_confidence_need_clarification():
    result = validate_and_build(ProposeInput(intent="帮我选股", confidence="low"))
    assert result.kind == "need_clarification"
    assert result.questions
