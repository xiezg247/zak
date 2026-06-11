"""行情表列定义与格式化。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.config import exchange_to_cn
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.domain.quote_time import format_trade_time_display
from vnpy_ashare.quotes.snapshot import QuoteSnapshot


@dataclass(frozen=True)
class QuoteTableColumn:
    key: str
    header: str
    price_colored: bool = False


QUOTE_TABLE_COLUMNS: tuple[QuoteTableColumn, ...] = (
    QuoteTableColumn("index", "序号"),
    QuoteTableColumn("symbol", "证券代码"),
    QuoteTableColumn("exchange", "交易所"),
    QuoteTableColumn("name", "证券名称"),
    QuoteTableColumn("last_price", "现价", True),
    QuoteTableColumn("change_pct", "涨幅%", True),
    QuoteTableColumn("change_amount", "涨跌", True),
    QuoteTableColumn("amplitude", "振幅%", True),
    QuoteTableColumn("turnover_rate", "换手%"),
    QuoteTableColumn("volume", "成交量"),
    QuoteTableColumn("amount", "成交额"),
    QuoteTableColumn("high_price", "最高", True),
    QuoteTableColumn("low_price", "最低", True),
    QuoteTableColumn("open_price", "今开", True),
    QuoteTableColumn("prev_close", "昨收"),
    QuoteTableColumn("trade_time", "更新时间"),
    QuoteTableColumn("signal", "信号"),
    QuoteTableColumn("signal_date", "信号日"),
    QuoteTableColumn("ref_buy_price", "参考买价", True),
    QuoteTableColumn("ref_sell_price", "参考卖价", True),
    QuoteTableColumn("dist_buy_pct", "距买价%", True),
    QuoteTableColumn("signal_strength", "强度"),
    QuoteTableColumn("signal_reason", "理由"),
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
    "状态",
]


def build_local_data_row(
    item: StockItem,
    index_text: str,
    *,
    start: str,
    end: str,
    count: str,
    status: str,
) -> list[str]:
    return [
        index_text,
        item.symbol,
        exchange_to_cn(item.exchange),
        item.name or "—",
        start,
        end,
        count,
        status,
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


def format_volume(volume: float) -> str:
    if volume <= 0:
        return "—"
    if volume >= 1e8:
        return f"{volume / 1e8:.2f}亿"
    if volume >= 1e4:
        return f"{volume / 1e4:.2f}万"
    return f"{volume:.0f}"


def format_amount(amount: float) -> str:
    if amount <= 0:
        return "—"
    if amount >= 1e8:
        return f"{amount / 1e8:.2f}亿"
    if amount >= 1e4:
        return f"{amount / 1e4:.2f}万"
    return f"{amount:.2f}"


def build_quote_row(
    item: StockItem,
    quote: QuoteSnapshot | None,
    index_text: str,
    tail_value: str = "",
    *,
    tail_values: list[str] | None = None,
) -> tuple[list[str], set[int]]:
    colored_cols: set[int] = set()
    values: list[str] = []

    if quote:
        field_map = {
            "index": index_text,
            "symbol": item.symbol,
            "exchange": exchange_to_cn(item.exchange),
            "name": quote.name or item.name,
            "last_price": f"{quote.last_price:.2f}",
            "change_pct": f"{quote.change_pct:+.2f}",
            "change_amount": f"{quote.change_amount:+.2f}",
            "amplitude": f"{quote.amplitude:.2f}",
            "turnover_rate": f"{quote.turnover_rate:.2f}",
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
