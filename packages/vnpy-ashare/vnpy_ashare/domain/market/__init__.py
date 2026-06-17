"""盘面与市场结构：指数、板块、资金流。"""

from vnpy_ashare.domain.market.board import matches_board
from vnpy_ashare.domain.market.index_amount import IndexAmountSeries
from vnpy_ashare.domain.market.indices import MARKET_INDEX_TS_CODES, MARKET_INDICES
from vnpy_ashare.domain.market.quote_row import (
    QuoteRow,
    QuoteRowLike,
    coerce_quote_row,
    coerce_quote_rows,
    quote_row_as_dict,
    quote_row_from_mapping,
    quote_row_from_stock_and_snapshot,
    quote_rows_by_vt,
    quote_rows_to_dicts,
)
from vnpy_ashare.domain.market.sector_flow import (
    SectorConstituentRow,
    SectorFlowHistoryPoint,
    SectorFlowRow,
    SectorFlowSnapshot,
)

__all__ = [
    "IndexAmountSeries",
    "MARKET_INDICES",
    "MARKET_INDEX_TS_CODES",
    "QuoteRow",
    "QuoteRowLike",
    "SectorConstituentRow",
    "SectorFlowHistoryPoint",
    "SectorFlowRow",
    "SectorFlowSnapshot",
    "coerce_quote_row",
    "coerce_quote_rows",
    "matches_board",
    "quote_row_as_dict",
    "quote_row_from_mapping",
    "quote_row_from_stock_and_snapshot",
    "quote_rows_by_vt",
    "quote_rows_to_dicts",
]
