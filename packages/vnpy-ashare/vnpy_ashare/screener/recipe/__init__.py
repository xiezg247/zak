"""多维度选股配方。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.recipe.recipe import (
    TriggerKind,
    list_recipe_catalog,
    resolve_recipe,
)

__all__ = [
    "TriggerKind",
    "build_reason_summary",
    "list_recipe_catalog",
    "resolve_recipe",
    "run_recipe",
    "run_recipe_object",
]


def __getattr__(name: str) -> Any:
    if name in {"build_reason_summary", "run_recipe", "run_recipe_object"}:
        from vnpy_ashare.screener.recipe.recipe_runner import (
            build_reason_summary,
            run_recipe,
            run_recipe_object,
        )

        return {
            "build_reason_summary": build_reason_summary,
            "run_recipe": run_recipe,
            "run_recipe_object": run_recipe_object,
        }[name]
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
