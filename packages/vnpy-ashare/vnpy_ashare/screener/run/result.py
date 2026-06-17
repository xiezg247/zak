"""选股执行结果类型（打破 runner ↔ industry_screen 循环）。"""

from __future__ import annotations

from vnpy_ashare.domain.screener.run_result import ScreenerRunResult, build_screener_run_result

__all__ = ["ScreenerRunResult", "build_screener_run_result"]
