"""配方 NL 映射测试。"""

from __future__ import annotations

from vnpy_ashare.screener.recipe import RECIPE_INTRADAY_MULTI
from vnpy_ashare.screener.recipe_nl_mapper import ProposeRecipeInput, validate_and_build_recipe


def test_propose_recipe_intraday_intent():
    result = validate_and_build_recipe(
        ProposeRecipeInput(intent="帮我跑盘中多因子选股", confidence="high"),
    )
    assert result.kind == "pending_confirm"
    assert result.draft is not None
    assert result.draft.recipe_id == RECIPE_INTRADAY_MULTI
    assert result.draft.trigger_kind == "intraday"


def test_propose_recipe_low_confidence():
    result = validate_and_build_recipe(
        ProposeRecipeInput(intent="选股", confidence="low"),
    )
    assert result.kind == "need_clarification"
    assert result.questions
