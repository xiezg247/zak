"""批量回测模板（Phase 5）：按 Profile / Recipe 预填策略、区间与参数。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import Field

from vnpy_ashare.screener.batch.batch_actions import BatchBacktestParams
from vnpy_ashare.screener.recipe.recipe import (
    RECIPE_CM20_ELASTIC,
    RECIPE_ULTRA_SHORT_FIRST_BOARD,
    RECIPE_ULTRA_SHORT_LIMIT,
)
from vnpy_common.domain.base import FrozenModel


class BatchBacktestTemplate(FrozenModel):
    template_id: str = Field(description="模板标识")
    title: str = Field(description="展示标题")
    class_name: str = Field(description="策略类名")
    lookback_days: int = Field(description="回测区间天数")
    strategy_setting: dict[str, Any] = Field(description="策略参数字典")
    note: str = Field(default="", description="补充说明")


_TEMPLATES: dict[str, BatchBacktestTemplate] = {
    "ultra_short_limit_board": BatchBacktestTemplate(
        template_id="ultra_short_limit_board",
        title="极致短线·打板",
        class_name="AshareLimitBoardStrategy",
        lookback_days=365,
        strategy_setting={
            "fast_window": 5,
            "slow_window": 10,
            "max_hold_days": 2,
            "stop_loss_pct": 0.05,
            "reject_one_word": True,
            "one_word_amplitude_max": 0.5,
        },
        note="日 K 涨停代理；信号侧封板时间来自 limit_list_d",
    ),
    "ultra_short_breakout": BatchBacktestTemplate(
        template_id="ultra_short_breakout",
        title="极致短线·半路",
        class_name="AshareIntradayBreakoutStrategy",
        lookback_days=365,
        strategy_setting={
            "fast_window": 5,
            "slow_window": 10,
            "min_change_pct": 3.0,
            "max_change_pct": 7.0,
            "volume_ratio_min": 1.5,
            "max_hold_days": 2,
            "stop_loss_pct": 0.03,
        },
        note="日 K 涨幅 3–7% + 量比半路代理",
    ),
    "short_swing": BatchBacktestTemplate(
        template_id="short_swing",
        title="短线波段·突破",
        class_name="AshareShortBreakoutStrategy",
        lookback_days=730,
        strategy_setting={
            "fast_window": 5,
            "slow_window": 10,
            "breakout_lookback": 5,
            "volume_ratio_min": 1.5,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06,
            "max_hold_days": 3,
        },
    ),
    "medium_watch": BatchBacktestTemplate(
        template_id="medium_watch",
        title="中线观察·双均线",
        class_name="AshareDoubleMaStrategy",
        lookback_days=1095,
        strategy_setting={"fast_window": 10, "slow_window": 20},
    ),
    "trend": BatchBacktestTemplate(
        template_id="trend",
        title="趋势中线",
        class_name="AshareTrendMaStrategy",
        lookback_days=1825,
        strategy_setting={
            "fast_window": 20,
            "slow_window": 60,
            "adx_period": 14,
            "adx_threshold": 25,
            "trailing_stop_pct": 0.12,
        },
    ),
}

_RECIPE_TEMPLATE: dict[str, str] = {
    RECIPE_ULTRA_SHORT_LIMIT: "ultra_short_limit_board",
    RECIPE_ULTRA_SHORT_FIRST_BOARD: "ultra_short_limit_board",
    RECIPE_CM20_ELASTIC: "ultra_short_breakout",
}

_PROFILE_TEMPLATE: dict[str, str] = {
    "ultra_short": "ultra_short_limit_board",
    "short_swing": "short_swing",
    "medium_watch": "medium_watch",
    "trend": "trend",
}


def resolve_batch_backtest_template_id(
    *,
    profile_id: str | None = None,
    recipe_id: str | None = None,
) -> str | None:
    rid = (recipe_id or "").strip()
    if rid and rid in _RECIPE_TEMPLATE:
        return _RECIPE_TEMPLATE[rid]
    pid = (profile_id or "").strip()
    if pid and pid in _PROFILE_TEMPLATE:
        return _PROFILE_TEMPLATE[pid]
    return None


def get_batch_backtest_template(template_id: str) -> BatchBacktestTemplate | None:
    return _TEMPLATES.get(template_id)


def apply_batch_backtest_template(
    params: BatchBacktestParams,
    *,
    profile_id: str | None = None,
    recipe_id: str | None = None,
    override_class_name: bool = True,
    override_dates: bool = True,
    override_setting: bool = True,
) -> BatchBacktestParams:
    """按 Profile / Recipe 合并批量回测默认参数。"""
    template_id = resolve_batch_backtest_template_id(profile_id=profile_id, recipe_id=recipe_id)
    if not template_id:
        return params
    template = _TEMPLATES.get(template_id)
    if template is None:
        return params

    end = params.end
    start = end - timedelta(days=template.lookback_days) if override_dates else params.start
    if start > end:
        start = end

    class_name = template.class_name if override_class_name else params.class_name
    setting: dict[str, Any] | None
    if override_setting:
        setting = dict(template.strategy_setting)
    elif params.strategy_setting is not None:
        setting = dict(params.strategy_setting)
    else:
        setting = None

    return params.model_copy(
        update={
            "class_name": class_name,
            "start": start,
            "end": end,
            "strategy_setting": setting,
        },
    )


def batch_backtest_template_note(
    *,
    profile_id: str | None = None,
    recipe_id: str | None = None,
) -> str:
    template_id = resolve_batch_backtest_template_id(profile_id=profile_id, recipe_id=recipe_id)
    if not template_id:
        return ""
    template = _TEMPLATES.get(template_id)
    if template is None:
        return ""
    parts = [template.title, f"近 {template.lookback_days} 日"]
    if template.note:
        parts.append(template.note)
    return " · ".join(parts)
