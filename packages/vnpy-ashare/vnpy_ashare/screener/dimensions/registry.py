"""维度注册表与统一调度。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.dimensions.intraday_breakout import run_intraday_breakout
from vnpy_ashare.screener.dimensions.low_pe import run_low_pe
from vnpy_ashare.screener.dimensions.momentum import run_momentum
from vnpy_ashare.screener.dimensions.moneyflow import run_moneyflow
from vnpy_ashare.screener.dimensions.moneyflow_intraday import run_moneyflow_intraday
from vnpy_ashare.screener.dimensions.sector_strength import run_sector_strength
from vnpy_ashare.screener.dimensions.sentiment_gate_dim import run_sentiment_gate
from vnpy_ashare.screener.dimensions.turnover import run_turnover
from vnpy_ashare.screener.dimensions.volume_ratio import run_volume_ratio
from vnpy_ashare.screener.dimensions.volume_surge import run_volume_surge
from vnpy_ashare.screener.recipe import DimensionSpec

DimensionRunner = Callable[..., tuple[list[DimensionHit], int]]

DIMENSION_RUNNERS: dict[str, DimensionRunner] = {
    "momentum": run_momentum,
    "turnover": run_turnover,
    "volume_ratio": run_volume_ratio,
    "volume_surge": run_volume_surge,
    "sector_strength": run_sector_strength,
    "intraday_breakout": run_intraday_breakout,
    "moneyflow_intraday": run_moneyflow_intraday,
    "sentiment_gate": run_sentiment_gate,
    "moneyflow": run_moneyflow,
    "low_pe": run_low_pe,
}

META_DIMENSION_IDS = frozenset({"sentiment_gate"})


def run_dimension(spec: DimensionSpec, pool_size: int) -> tuple[list[DimensionHit], int]:
    if spec.dimension_id in META_DIMENSION_IDS:
        return [], 0
    runner = DIMENSION_RUNNERS.get(spec.dimension_id)
    if runner is None:
        return [], 0
    return runner(pool_size, weight=spec.weight)


def scoring_dimension_specs(specs: list[DimensionSpec]) -> list[DimensionSpec]:
    """排除元维度（如 sentiment_gate），供并行打分与 min_dimensions 统计。"""
    return [spec for spec in specs if spec.dimension_id not in META_DIMENSION_IDS]
