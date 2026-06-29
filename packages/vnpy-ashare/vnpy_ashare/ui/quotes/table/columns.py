"""行情表列定义与格式化。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.runtime import exchange_to_cn
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.time.quote_time import format_trade_time_display
from vnpy_ashare.quotes.format import (
    format_amount,
    format_net_mf_amount,
    format_volume,
)
from vnpy_common.domain.base import FrozenModel


class QuoteTableColumn(FrozenModel):
    key: str = Field(description="键名")
    header: str = Field(description="表头文案")
    price_colored: bool = Field(default=False, description="是否按涨跌着色")


QUOTE_TABLE_COLUMNS: tuple[QuoteTableColumn, ...] = (
    QuoteTableColumn(key="index", header="序号"),
    QuoteTableColumn(key="symbol", header="证券代码"),
    QuoteTableColumn(key="exchange", header="交易所"),
    QuoteTableColumn(key="name", header="证券名称"),
    QuoteTableColumn(key="industry", header="行业"),
    QuoteTableColumn(key="market_board", header="板块"),
    QuoteTableColumn(key="last_price", header="现价", price_colored=True),
    QuoteTableColumn(key="change_pct", header="涨幅%", price_colored=True),
    QuoteTableColumn(key="limit_times", header="连板"),
    QuoteTableColumn(key="change_speed_5m", header="5分涨速%", price_colored=True),
    QuoteTableColumn(key="change_amount", header="涨跌", price_colored=True),
    QuoteTableColumn(key="amplitude", header="振幅%", price_colored=True),
    QuoteTableColumn(key="turnover_rate", header="换手%"),
    QuoteTableColumn(key="volume_ratio", header="量比"),
    QuoteTableColumn(key="net_mf_amount", header="主力净流入"),
    QuoteTableColumn(key="volume", header="成交量"),
    QuoteTableColumn(key="amount", header="成交额"),
    QuoteTableColumn(key="high_price", header="最高", price_colored=True),
    QuoteTableColumn(key="low_price", header="最低", price_colored=True),
    QuoteTableColumn(key="open_price", header="今开", price_colored=True),
    QuoteTableColumn(key="prev_close", header="昨收"),
    QuoteTableColumn(key="trade_time", header="更新时间"),
    QuoteTableColumn(key="signal", header="信号"),
    QuoteTableColumn(key="signal_date", header="信号日"),
    QuoteTableColumn(key="ref_buy_price", header="支撑锚点", price_colored=True),
    QuoteTableColumn(key="ref_sell_price", header="阻力锚点", price_colored=True),
    QuoteTableColumn(key="dist_buy_pct", header="距支撑%", price_colored=True),
    QuoteTableColumn(key="signal_strength", header="强度"),
    QuoteTableColumn(key="signal_reason", header="理由"),
)


def quote_column_index(key: str) -> int:
    for index, column in enumerate(QUOTE_TABLE_COLUMNS):
        if column.key == key:
            return index
    raise KeyError(key)


LOCAL_TABLE_HEADERS: list[str] = [
    "序号",
    "证券代码",
    "交易所",
    "证券名称",
    "起始",
    "结束",
    "K线数",
]


def build_local_data_row(
    item: StockItem,
    index_text: str,
    *,
    start: str,
    end: str,
    count: str,
) -> list[str]:
    return [
        index_text,
        item.symbol,
        exchange_to_cn(item.exchange),
        item.name or "—",
        start,
        end,
        count,
    ]


def quote_table_headers(
    *,
    tail_header: str | None = None,
    tail_headers: list[str] | None = None,
) -> list[str]:
    base = [column.header for column in QUOTE_TABLE_COLUMNS]
    if tail_headers is not None:
        return base + tail_headers
    if tail_header is not None:
        return base + [tail_header]
    return base


def format_limit_times(boards: float) -> str:
    if boards < 1:
        return "—"
    value = int(boards)
    if float(value) == boards:
        return f"{value}板"
    return f"{boards:.1f}板"


def build_quote_row(
    item: StockItem,
    quote: QuoteSnapshot | None,
    index_text: str,
    tail_value: str = "",
    *,
    tail_values: list[str] | None = None,
    industry: str = "",
    market_board: str = "",
) -> tuple[list[str], set[int]]:
    colored_cols: set[int] = set()
    values: list[str] = []

    if quote:
        field_map = {
            "index": index_text,
            "symbol": item.symbol,
            "exchange": exchange_to_cn(item.exchange),
            "name": item.name or quote.name,
            "last_price": f"{quote.last_price:.2f}",
            "change_pct": f"{quote.change_pct:+.2f}",
            "limit_times": format_limit_times(quote.limit_times),
            "change_speed_5m": f"{quote.change_speed_5m:+.2f}" if quote.change_speed_5m != 0 else "—",
            "change_amount": f"{quote.change_amount:+.2f}",
            "amplitude": f"{quote.amplitude:.2f}",
            "turnover_rate": f"{quote.turnover_rate:.2f}",
            "volume_ratio": f"{quote.volume_ratio:.2f}" if quote.volume_ratio > 0 else "—",
            "net_mf_amount": format_net_mf_amount(quote.net_mf_amount),
            "volume": format_volume(quote.volume),
            "amount": format_amount(quote.amount),
            "high_price": f"{quote.high_price:.2f}",
            "low_price": f"{quote.low_price:.2f}",
            "open_price": f"{quote.open_price:.2f}",
            "prev_close": f"{quote.prev_close:.2f}",
            "trade_time": format_trade_time_display(quote.trade_time),
        }
    else:
        field_map = {
            "index": index_text,
            "symbol": item.symbol,
            "exchange": exchange_to_cn(item.exchange),
            "name": item.name,
        }

    field_map["industry"] = industry or "—"
    field_map["market_board"] = market_board or "—"

    for col_index, column in enumerate(QUOTE_TABLE_COLUMNS):
        if column.key in field_map:
            values.append(field_map[column.key])
        else:
            values.append("—")
        if quote and column.price_colored:
            colored_cols.add(col_index)

    if tail_values is not None:
        values.extend(tail_values)
    else:
        values.append(tail_value)
    return values, colored_cols
