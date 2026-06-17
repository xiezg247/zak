"""领域模型与 A 股通用规则。

子包::

    core/      数值解析、环境变量
    time/      东八区时间、交易日历、交易时段、行情时间
    symbols/   标的代码互转（TickFlow / Tushare / vt_symbol）
    market/    指数、板块、资金流
    trading/   记账、计划、持仓、策略信号
    models/    笔记等领域实体
    tech/      技术指标纯函数
    ai/        AI 触发的 UI 写操作
"""

from vnpy_ashare.domain.core.numbers import coerce_float, float_or_none, safe_float
from vnpy_ashare.domain.symbols import (
    StockItem,
    parse_stock_symbol,
    parse_tickflow_symbol,
    symbol_exchange_to_tickflow,
    symbol_exchange_to_ts_code,
    ts_code_to_vt_symbol,
    vt_symbol_to_symbol,
    vt_symbol_to_ts_code,
)
from vnpy_ashare.quotes.format import (
    format_amount,
    format_net_mf_amount,
    format_pct,
    format_volume,
)

__all__ = [
    "StockItem",
    "coerce_float",
    "format_amount",
    "format_net_mf_amount",
    "format_pct",
    "format_volume",
    "float_or_none",
    "parse_stock_symbol",
    "parse_tickflow_symbol",
    "safe_float",
    "symbol_exchange_to_tickflow",
    "symbol_exchange_to_ts_code",
    "ts_code_to_vt_symbol",
    "vt_symbol_to_symbol",
    "vt_symbol_to_ts_code",
]
