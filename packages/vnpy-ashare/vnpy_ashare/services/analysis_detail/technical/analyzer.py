"""TechnicalAnalyzer：组合各 Mixin 的技术面编排入口。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.services.analysis_detail.technical.pattern import TechnicalPatternMixin
from vnpy_ashare.services.analysis_detail.technical.scenario import TechnicalScenarioMixin
from vnpy_ashare.services.analysis_detail.technical.screening import TechnicalScreeningMixin
from vnpy_ashare.services.analysis_detail.technical.signals import TechnicalSignalsMixin
from vnpy_ashare.services.analysis_detail.technical.snapshot import TechnicalSnapshotMixin

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine


class TechnicalAnalyzer(
    TechnicalSnapshotMixin,
    TechnicalPatternMixin,
    TechnicalScenarioMixin,
    TechnicalSignalsMixin,
    TechnicalScreeningMixin,
):
    def __init__(self, engine: AshareEngine) -> None:
        self._engine = engine
        self._benchmark_return_cache_key: int | None = None
        self._benchmark_return_cache_val: float | None = None

    def reset_benchmark_cache(self) -> None:
        self._benchmark_return_cache_key = None
        self._benchmark_return_cache_val = None
