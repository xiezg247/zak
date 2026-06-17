"""选股领域模型。"""

from vnpy_ashare.domain.screener.result_row import (
    ScreenerResultRow,
    ScreeningRowLike,
    coerce_screener_result_row,
    coerce_screener_result_rows,
    screener_rows_from_mappings,
    screener_rows_to_dicts,
)

__all__ = [
    "ScreeningRowLike",
    "ScreenerResultRow",
    "coerce_screener_result_row",
    "coerce_screener_result_rows",
    "screener_rows_from_mappings",
    "screener_rows_to_dicts",
]
