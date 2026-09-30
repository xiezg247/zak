"""维度注册表与统一调度（runner 按需惰性导入）。"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from vnpy_ashare.domain.screener.dimension_hit import DimensionHit
from vnpy_ashare.screener.recipe.recipe import DimensionSpec

DimensionRunner = Callable[..., tuple[list[DimensionHit], int]]

# dimension_id -> (module, attr)
_RUNNER_SPECS: dict[str, tuple[str, str]] = {
    "momentum": ("vnpy_ashare.screener.engine.dimensions.momentum", "run_momentum"),
    "turnover": ("vnpy_ashare.screener.engine.dimensions.turnover", "run_turnover"),
    "volume_ratio": ("vnpy_ashare.screener.engine.dimensions.volume_ratio", "run_volume_ratio"),
    "volume_surge": ("vnpy_ashare.screener.engine.dimensions.volume_surge", "run_volume_surge"),
    "sector_strength": ("vnpy_ashare.screener.engine.dimensions.sector_strength", "run_sector_strength"),
    "concept_strength": ("vnpy_ashare.screener.engine.dimensions.concept_strength", "run_concept_strength"),
    "intraday_breakout": ("vnpy_ashare.screener.engine.dimensions.intraday_breakout", "run_intraday_breakout"),
    "limit_board": ("vnpy_ashare.screener.engine.dimensions.limit_board", "run_limit_board"),
    "first_board": ("vnpy_ashare.screener.engine.dimensions.first_board", "run_first_board"),
    "leader_score": ("vnpy_ashare.screener.engine.dimensions.radar_resonance", "run_leader_score"),
    "radar_resonance": ("vnpy_ashare.screener.engine.dimensions.radar_resonance", "run_radar_resonance"),
    "cm20_elastic": ("vnpy_ashare.screener.engine.dimensions.cm20_elastic", "run_cm20_elastic"),
    "moneyflow_intraday": ("vnpy_ashare.screener.engine.dimensions.moneyflow_resolve", "run_moneyflow_intraday"),
    "sentiment_gate": ("vnpy_ashare.screener.dimensions.sentiment_gate_dim", "run_sentiment_gate"),
    "moneyflow": ("vnpy_ashare.screener.engine.dimensions.moneyflow", "run_moneyflow"),
    "low_pe": ("vnpy_ashare.screener.engine.dimensions.low_pe", "run_low_pe"),
}

META_DIMENSION_IDS = frozenset({"sentiment_gate"})

_runner_cache: dict[str, DimensionRunner] = {}


def _load_runner(dimension_id: str) -> DimensionRunner | None:
    cached = _runner_cache.get(dimension_id)
    if cached is not None:
        return cached
    spec = _RUNNER_SPECS.get(dimension_id)
    if spec is None:
        return None
    module_name, attr = spec
    module = importlib.import_module(module_name)
    runner = getattr(module, attr)
    _runner_cache[dimension_id] = runner
    return runner


class _LazyRunners(dict[str, DimensionRunner]):
    """兼容仍读取 DIMENSION_RUNNERS[...] 的代码；按 key 惰性导入。"""

    def __getitem__(self, key: str) -> DimensionRunner:
        runner = _load_runner(key)
        if runner is None:
            raise KeyError(key)
        return runner

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        runner = _load_runner(key)
        return default if runner is None else runner

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in _RUNNER_SPECS

    def keys(self):  # type: ignore[override]
        return _RUNNER_SPECS.keys()

    def __iter__(self):
        return iter(_RUNNER_SPECS)

    def __len__(self) -> int:
        return len(_RUNNER_SPECS)


DIMENSION_RUNNERS: dict[str, DimensionRunner] = _LazyRunners()


def run_dimension(spec: DimensionSpec, pool_size: int) -> tuple[list[DimensionHit], int]:
    if spec.dimension_id in META_DIMENSION_IDS:
        return [], 0
    runner = _load_runner(spec.dimension_id)
    if runner is None:
        return [], 0
    return runner(pool_size, weight=spec.weight)


def scoring_dimension_specs(specs: list[DimensionSpec]) -> list[DimensionSpec]:
    """排除元维度（如 sentiment_gate），供并行打分与 min_dimensions 统计。"""
    return [spec for spec in specs if spec.dimension_id not in META_DIMENSION_IDS]
