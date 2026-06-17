"""选股领域模型。"""

from vnpy_ashare.domain.screener.dimension_hit import DimensionHit, dimension_hit_row
from vnpy_ashare.domain.screener.page_context import BacktestSummary, ScreeningResultContext
from vnpy_ashare.domain.screener.predict import BaselinePredictHit, PredictHit
from vnpy_ashare.domain.screener.quotes_snapshot import MarketQuotesSnapshot
from vnpy_ashare.domain.screener.recipe import (
    RECIPE_CM20_ELASTIC,
    RECIPE_EMOTION_GATE_ONLY,
    RECIPE_INTRADAY_AGGRESSIVE,
    RECIPE_INTRADAY_MULTI,
    RECIPE_POST_CLOSE_MULTI,
    RECIPE_ULTRA_SHORT_FIRST_BOARD,
    RECIPE_ULTRA_SHORT_LIMIT,
    DimensionSpec,
    RecipeCatalogEntry,
    ScreenRecipe,
    TriggerKind,
)
from vnpy_ashare.domain.screener.result_row import (
    ScreenerResultRow,
    ScreeningRowLike,
    coerce_screener_result_row,
    coerce_screener_result_rows,
    screener_rows_from_mappings,
    screener_rows_to_dicts,
    screening_row_to_dict,
)
from vnpy_ashare.domain.screener.run_result import ScreenerRunResult, build_screener_run_result

__all__ = [
    "BacktestSummary",
    "BaselinePredictHit",
    "DimensionHit",
    "DimensionSpec",
    "MarketQuotesSnapshot",
    "PredictHit",
    "RECIPE_CM20_ELASTIC",
    "RECIPE_EMOTION_GATE_ONLY",
    "RECIPE_INTRADAY_AGGRESSIVE",
    "RECIPE_INTRADAY_MULTI",
    "RECIPE_POST_CLOSE_MULTI",
    "RECIPE_ULTRA_SHORT_FIRST_BOARD",
    "RECIPE_ULTRA_SHORT_LIMIT",
    "RecipeCatalogEntry",
    "ScreenRecipe",
    "ScreeningResultContext",
    "ScreeningRowLike",
    "ScreenerResultRow",
    "ScreenerRunResult",
    "TriggerKind",
    "build_screener_run_result",
    "coerce_screener_result_row",
    "coerce_screener_result_rows",
    "dimension_hit_row",
    "screener_rows_from_mappings",
    "screener_rows_to_dicts",
    "screening_row_to_dict",
]
