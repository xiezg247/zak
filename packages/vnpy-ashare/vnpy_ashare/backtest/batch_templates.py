"""批量回测模板（Phase 5）：按 Profile / Recipe 预填策略、区间与参数。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import Field
from vnpy.trader.constant import Interval

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
    interval: Interval = Field(default=Interval.DAILY, description="K 线周期")


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
    "ultra_short_limit_board_minute": BatchBacktestTemplate(
        template_id="ultra_short_limit_board_minute",
        title="极致短线·打板（分 K）",
        class_name="AshareLimitBoardMinuteStrategy",
        lookback_days=90,
        strategy_setting={
            "max_hold_days": 2,
            "stop_loss_pct": 0.05,
            "reject_one_word": True,
            "one_word_amplitude_max": 0.5,
            "seal_cutoff_minutes": 630,
            "reject_broken": True,
        },
        note="1 分 K 触板规则；须本地 1m 数据，回测周期建议 ≤90 日",
        interval=Interval.MINUTE,
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
    "ultra_short_breakout_minute": BatchBacktestTemplate(
        template_id="ultra_short_breakout_minute",
        title="极致短线·半路（分 K）",
        class_name="AshareIntradayBreakoutMinuteStrategy",
        lookback_days=90,
        strategy_setting={
            "min_change_pct": 3.0,
            "max_change_pct": 7.0,
            "volume_ratio_min": 1.2,
            "window_start_minutes": 580,
            "window_end_minutes": 630,
            "max_hold_days": 2,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.08,
        },
        note="1 分 K 9:40–10:30 半路；须本地 1m 数据，回测周期建议 ≤90 日",
        interval=Interval.MINUTE,
    ),
    "ultra_short_pullback_minute": BatchBacktestTemplate(
        template_id="ultra_short_pullback_minute",
        title="极致短线·低吸（分 K）",
        class_name="AsharePullbackMinuteStrategy",
        lookback_days=90,
        strategy_setting={
            "ma_window": 5,
            "pullback_band_pct": 2.0,
            "min_dip_pct": -5.0,
            "max_dip_pct": -3.0,
            "window_start_minutes": 870,
            "window_end_minutes": 900,
            "max_hold_days": 3,
            "stop_loss_pct": 0.05,
        },
        note="1 分 K 14:30 后承接；须本地 1m + 日 K，回测周期建议 ≤90 日",
        interval=Interval.MINUTE,
    ),
    "ultra_short_overnight_exit_minute": BatchBacktestTemplate(
        template_id="ultra_short_overnight_exit_minute",
        title="极致短线·隔日退出（分 K）",
        class_name="AshareOvernightExitMinuteStrategy",
        lookback_days=90,
        strategy_setting={
            "stop_loss_pct": 0.05,
            "stop_minutes": 30,
            "max_hold_days": 2,
            "entry_at_session_close": True,
        },
        note="日末建仓 + 次日分 K 隔日规则；须本地 1m",
        interval=Interval.MINUTE,
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

_TRIGGER_TEMPLATE: dict[str, str] = {
    "radar_leader": "ultra_short_limit_board",
}

# UI 下拉顺序：日 K 模板 → 分 K 模板
_UI_TEMPLATE_ORDER: tuple[str, ...] = (
    "ultra_short_limit_board",
    "ultra_short_breakout",
    "short_swing",
    "medium_watch",
    "trend",
    "ultra_short_limit_board_minute",
    "ultra_short_breakout_minute",
    "ultra_short_pullback_minute",
    "ultra_short_overnight_exit_minute",
)


def list_batch_backtest_template_choices() -> list[tuple[str, str]]:
    """批量回测模板下拉项：(template_id, label)。空 id 表示跟随来源自动推断。"""
    items: list[tuple[str, str]] = [("", "自动（跟随来源）")]
    daily: list[tuple[str, str]] = []
    minute: list[tuple[str, str]] = []
    for template_id in _UI_TEMPLATE_ORDER:
        template = _TEMPLATES.get(template_id)
        if template is None:
            continue
        label = f"{template.title}（近 {template.lookback_days} 日）"
        if template.interval == Interval.MINUTE:
            minute.append((template_id, f"分 K · {label}"))
        else:
            daily.append((template_id, f"日 K · {label}"))
    items.extend(daily)
    items.extend(minute)
    return items


def format_batch_backtest_template_note(template_id: str) -> str:
    """按模板 ID 生成对话框说明文案。"""
    tid = (template_id or "").strip()
    if not tid:
        return ""
    template = _TEMPLATES.get(tid)
    if template is None:
        return ""
    parts = [template.title, f"近 {template.lookback_days} 日"]
    if template.interval == Interval.MINUTE:
        parts.insert(0, "分 K")
    if template.note:
        parts.append(template.note)
    return " · ".join(parts)


def resolve_batch_backtest_template_id(
    *,
    profile_id: str | None = None,
    recipe_id: str | None = None,
    trigger: str | None = None,
) -> str | None:
    trig = (trigger or "").strip()
    if trig and trig in _TRIGGER_TEMPLATE:
        return _TRIGGER_TEMPLATE[trig]
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
    trigger: str | None = None,
    template_id: str | None = None,
    override_class_name: bool = True,
    override_dates: bool = True,
    override_setting: bool = True,
) -> BatchBacktestParams:
    """按 Profile / Recipe / 选股 trigger / 模板 ID 合并批量回测默认参数。"""
    resolved_id = (template_id or "").strip() or resolve_batch_backtest_template_id(
        profile_id=profile_id,
        recipe_id=recipe_id,
        trigger=trigger,
    )
    if not resolved_id:
        return params
    template = _TEMPLATES.get(resolved_id)
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
            "interval": template.interval,
        },
    )


def batch_backtest_template_note(
    *,
    profile_id: str | None = None,
    recipe_id: str | None = None,
    trigger: str | None = None,
    template_id: str | None = None,
) -> str:
    resolved = (template_id or "").strip() or resolve_batch_backtest_template_id(
        profile_id=profile_id,
        recipe_id=recipe_id,
        trigger=trigger,
    )
    if not resolved:
        return ""
    return format_batch_backtest_template_note(resolved)
