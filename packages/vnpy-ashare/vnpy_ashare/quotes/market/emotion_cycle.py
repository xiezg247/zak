"""情绪周期引擎：五阶段标签 + 仓位系数 + 允许模式。"""

from __future__ import annotations

from vnpy_ashare.domain.market.breadth import MarketBreadthSnapshot
from vnpy_ashare.domain.market.emotion import (
    EmotionCycleInputs,
    EmotionCycleSnapshot,
    EmotionMode,
    EmotionStage,
)
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.quotes.market.emotion_cycle_cache import (
    invalidate_emotion_cycle_cache,
    peek_emotion_cycle_snapshot,
    store_emotion_cycle_snapshot,
)
from vnpy_ashare.quotes.market.emotion_cycle_inputs import build_emotion_cycle_inputs
from vnpy_ashare.quotes.market.market_overview_loaders import _load_breadth
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows
from vnpy_common.domain.serialize import dump_python

__all__ = [
    "EmotionCycleInputs",
    "EmotionCycleSnapshot",
    "EmotionCycleTracker",
    "EmotionMode",
    "EmotionStage",
    "classify_emotion_cycle",
    "format_mode_label",
    "invalidate_emotion_cycle_cache",
    "load_emotion_cycle_snapshot",
    "peek_emotion_cycle_snapshot",
    "store_emotion_cycle_snapshot",
]

_STAGE_LABELS: dict[EmotionStage, str] = {
    "ice": "冰点",
    "startup": "启动",
    "climax": "发酵/高潮",
    "divergence": "分歧",
    "recession": "退潮",
}

_STAGE_POSITION: dict[EmotionStage, tuple[float, float]] = {
    "ice": (0.0, 0.10),
    "startup": (0.30, 0.50),
    "climax": (0.60, 0.80),
    "divergence": (0.0, 0.30),
    "recession": (0.0, 0.0),
}

_STAGE_MODES: dict[EmotionStage, tuple[EmotionMode, ...]] = {
    "ice": (),
    "startup": ("limit_board", "halfway"),
    "climax": ("limit_board", "halfway"),
    "divergence": ("pullback",),
    "recession": (),
}

_MODE_LABELS: dict[EmotionMode, str] = {
    "limit_board": "打板",
    "halfway": "半路",
    "pullback": "低吸",
}

_AMOUNT_FLOOR = 1e12
_FEAR_GREED_OVERHEAT = 85.0


def format_mode_label(mode: str) -> str:
    if mode == "limit_board":
        return _MODE_LABELS["limit_board"]
    if mode == "halfway":
        return _MODE_LABELS["halfway"]
    if mode == "pullback":
        return _MODE_LABELS["pullback"]
    return mode


def _now_text() -> str:
    return format_china_datetime()


def _classify_stage(inputs: EmotionCycleInputs) -> EmotionStage:
    """判定顺序：退潮 → 冰点 → 高潮 → 分歧 → 启动 → 默认分歧。"""
    limit_up = inputs.limit_up_count
    limit_down = inputs.limit_down_count
    up_ratio = inputs.up_ratio
    max_boards = inputs.max_limit_times
    ladder_depth = inputs.limit_ladder_depth

    if limit_down >= 20:
        return "recession"
    if max_boards <= 2 and limit_down >= 15 and up_ratio < 0.35:
        return "ice"
    if ladder_depth >= 3 and limit_up >= 80:
        return "climax"
    if limit_up >= 30 and abs(limit_up - limit_down) <= 10:
        return "divergence"
    if max_boards >= 3 or limit_up >= 50:
        return "startup"
    return "divergence"


def classify_emotion_cycle(inputs: EmotionCycleInputs) -> EmotionCycleSnapshot:
    stage = _classify_stage(inputs)
    pct_min, pct_max = _STAGE_POSITION[stage]
    factor = (pct_min + pct_max) / 2.0 if pct_max > 0 else 0.0
    warnings: list[str] = []
    modes = list(_STAGE_MODES[stage])

    if inputs.total_amount > 0 and inputs.total_amount < _AMOUNT_FLOOR:
        factor *= 0.7
        warnings.append("成交额不足 1 万亿，建议降仓")

    if inputs.index_above_ma5 is False:
        factor *= 0.8
        modes = [mode for mode in modes if mode != "limit_board"]
        warnings.append("大盘 5 日线向下，回避打板")

    if inputs.fear_greed_index is not None and inputs.fear_greed_index > _FEAR_GREED_OVERHEAT:
        warnings.append(f"恐贪 {inputs.fear_greed_index:.0f} 偏高，注意过热")

    updated_at = inputs.updated_at or _now_text()
    return EmotionCycleSnapshot(
        stage=stage,
        stage_label=_STAGE_LABELS[stage],
        position_pct_min=pct_min,
        position_pct_max=pct_max,
        position_factor=min(1.0, max(0.0, factor)),
        allowed_modes=tuple(modes),
        allow_new_positions=stage not in {"recession", "ice"},
        warnings=tuple(warnings),
        inputs=dump_python(inputs),
        updated_at=updated_at,
    )


def load_emotion_cycle_snapshot(
    *,
    breadth: MarketBreadthSnapshot | None = None,
    fetch_if_missing: bool = False,
) -> EmotionCycleSnapshot | None:
    """从广度或行情缓存计算情绪周期。

    默认不拉全市场行情（``fetch_if_missing=False``），无缓存时返回 None；
    显式分析 / 流水记账等场景再传 ``fetch_if_missing=True``。
    """
    cache_only = False
    if breadth is None:
        peeked = peek_emotion_cycle_snapshot()
        if peeked is not None:
            return peeked

        cached = get_market_quotes_cache()
        if cached:
            rows, updated_at = cached, None
            cache_only = True
        elif fetch_if_missing:
            try:
                snapshot = load_market_quote_rows()
                rows = snapshot.rows
                updated_at = snapshot.updated_at
            except MarketQuotesLoadError:
                return None
        else:
            return None
        breadth = _load_breadth(rows, updated_at=updated_at)
    if breadth is None:
        return None
    inputs = build_emotion_cycle_inputs(breadth, include_auxiliary=not cache_only)
    result = classify_emotion_cycle(inputs)
    store_emotion_cycle_snapshot(result)
    return result


class EmotionCycleTracker:
    """阶段变更检测（供通知）。"""

    def __init__(self) -> None:
        self._last_stage: EmotionStage | None = None
        self._last_snapshot: EmotionCycleSnapshot | None = None

    @property
    def last_snapshot(self) -> EmotionCycleSnapshot | None:
        return self._last_snapshot

    def update(self, inputs: EmotionCycleInputs) -> EmotionCycleSnapshot | None:
        snapshot = classify_emotion_cycle(inputs)
        self._last_snapshot = snapshot
        if snapshot.stage == self._last_stage:
            return None
        self._last_stage = snapshot.stage
        return snapshot

    def update_from_breadth(self, breadth: MarketBreadthSnapshot) -> EmotionCycleSnapshot | None:
        return self.update(build_emotion_cycle_inputs(breadth))
