"""TickFlow 应用层集成（行情、WebSocket、盘口、K 线、标的同步）。

实时 / 盘中走本包；**历史 K 线（日 K / 分 K）同步走 Tushare**（见 ``integrations.tushare.bars``）。
低层 SDK 与 VeighNa datafeed 见 ``vnpy_tickflow``。
"""

from vnpy_ashare.integrations.tickflow.depth import DepthPermissionError, fetch_depth_from_tickflow
from vnpy_ashare.integrations.tickflow.klines import (
    dataframe_to_bars,
    fetch_history_bars,
    fetch_intraday_bars,
    fetch_minute_bars,
)
from vnpy_ashare.integrations.tickflow.quotes import (
    MARKET_INDICES,
    QUOTE_BATCH_SIZE,
    fetch_index_ticker,
    fetch_quotes_from_tickflow,
    get_tickflow_client,
    parse_quote_row,
    quote_fetch_max_workers,
)
from vnpy_ashare.integrations.tickflow.stream import TickflowStreamBridge, can_use_tickflow_stream
from vnpy_ashare.integrations.tickflow.universe import UNIVERSE_ID, fetch_universe_items

__all__ = [
    "DepthPermissionError",
    "MARKET_INDICES",
    "QUOTE_BATCH_SIZE",
    "TickflowStreamBridge",
    "UNIVERSE_ID",
    "can_use_tickflow_stream",
    "dataframe_to_bars",
    "fetch_depth_from_tickflow",
    "fetch_history_bars",
    "fetch_index_ticker",
    "fetch_intraday_bars",
    "fetch_minute_bars",
    "fetch_quotes_from_tickflow",
    "fetch_universe_items",
    "get_tickflow_client",
    "parse_quote_row",
    "quote_fetch_max_workers",
]
