"""批量回测模板测试。"""

from __future__ import annotations

from datetime import datetime

from vnpy.trader.constant import Interval

from vnpy_ashare.backtest.batch_templates import (
    apply_batch_backtest_template,
    get_batch_backtest_template,
    resolve_batch_backtest_template_id,
)
from vnpy_ashare.screener.batch.batch_actions import BatchBacktestParams
from vnpy_ashare.screener.recipe.recipe import RECIPE_ULTRA_SHORT_LIMIT


def _base_params() -> BatchBacktestParams:
    return BatchBacktestParams(
        class_name="AshareDoubleMaStrategy",
        start=datetime(2020, 1, 1),
        end=datetime(2025, 6, 1),
    )


def test_resolve_recipe_ultra_short_limit() -> None:
    assert resolve_batch_backtest_template_id(recipe_id=RECIPE_ULTRA_SHORT_LIMIT) == "ultra_short_limit_board"


def test_resolve_radar_leader_trigger() -> None:
    assert resolve_batch_backtest_template_id(trigger="radar_leader") == "ultra_short_limit_board"


def test_apply_radar_leader_trigger() -> None:
    params = _base_params()
    merged = apply_batch_backtest_template(params, trigger="radar_leader")
    assert merged.class_name == "AshareLimitBoardStrategy"
    assert merged.strategy_setting is not None
    assert merged.strategy_setting["max_hold_days"] == 2
    assert merged.interval == Interval.DAILY


def test_apply_minute_limit_board_template() -> None:
    params = _base_params()
    merged = apply_batch_backtest_template(params, template_id="ultra_short_limit_board_minute")
    assert merged.class_name == "AshareLimitBoardMinuteStrategy"
    assert merged.interval == Interval.MINUTE
    assert merged.strategy_setting is not None
    assert merged.strategy_setting["seal_cutoff_minutes"] == 630
    assert (merged.end - merged.start).days == 90


def test_apply_ultra_short_recipe_overrides_strategy_and_window() -> None:
    params = _base_params()
    merged = apply_batch_backtest_template(params, recipe_id=RECIPE_ULTRA_SHORT_LIMIT)
    assert merged.class_name == "AshareLimitBoardStrategy"
    assert merged.strategy_setting is not None
    assert merged.strategy_setting["max_hold_days"] == 2
    assert (merged.end - merged.start).days == 365


def test_apply_profile_keeps_class_when_override_disabled() -> None:
    params = _base_params()
    merged = apply_batch_backtest_template(
        params,
        profile_id="ultra_short",
        override_class_name=False,
        override_setting=False,
    )
    assert merged.class_name == "AshareDoubleMaStrategy"
    assert (merged.end - merged.start).days == 365


def test_get_minute_template_metadata() -> None:
    tpl = get_batch_backtest_template("ultra_short_limit_board_minute")
    assert tpl is not None
    assert tpl.class_name == "AshareLimitBoardMinuteStrategy"
    assert tpl.interval == Interval.MINUTE
