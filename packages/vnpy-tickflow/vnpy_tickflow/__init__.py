"""vnpy_tickflow：TickFlow 数据源与共享客户端。"""

from vnpy_tickflow.client import get_tickflow_client, is_free_mode, resolve_tickflow_api_key
from vnpy_tickflow.datafeed import TickflowDatafeed
from vnpy_tickflow.klines import MAX_BARS_PER_REQUEST, fetch_klines_paged
from vnpy_tickflow.mapping import (
    ASHARE_EXCHANGES,
    CHINA_TZ,
    FREE_PERIODS,
    interval_to_period,
    parse_datetime,
    to_tf_symbol,
)

Datafeed = TickflowDatafeed

__all__ = [
    "ASHARE_EXCHANGES",
    "CHINA_TZ",
    "Datafeed",
    "FREE_PERIODS",
    "MAX_BARS_PER_REQUEST",
    "TickflowDatafeed",
    "fetch_klines_paged",
    "get_tickflow_client",
    "interval_to_period",
    "is_free_mode",
    "parse_datetime",
    "resolve_tickflow_api_key",
    "to_tf_symbol",
]
