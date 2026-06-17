"""TechnicalAnalyzer Mixin 共享类型（供 mypy 识别 _engine 等属性）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine


class _TechnicalAnalyzerBase(Protocol):
    _engine: AshareEngine
    _benchmark_return_cache_key: int | None
    _benchmark_return_cache_val: float | None

    def reset_benchmark_cache(self) -> None: ...

    def technical_snapshot(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        scope: str = "daily",
    ) -> dict[str, Any]: ...

    def historical_pattern_summary(
        self,
        symbol: str,
        *,
        lookback: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]: ...

    def _build_signal_payload(
        self,
        symbol: str,
        *,
        class_name: str,
        lookback: int,
        fast_window: int,
        slow_window: int,
        scope: str,
    ) -> dict[str, Any] | None: ...
