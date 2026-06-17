"""多因子选股维度插件。"""

from __future__ import annotations

from typing import Any

__all__ = ["run_dimension"]


def __getattr__(name: str) -> Any:
    if name == "run_dimension":
        from vnpy_ashare.screener.dimensions.registry import run_dimension

        return run_dimension
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
