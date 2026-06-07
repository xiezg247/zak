"""A 股标的统一数据模型。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy.trader.constant import Exchange

SUFFIX_TO_EXCHANGE: dict[str, Exchange] = {
    "SH": Exchange.SSE,
    "SZ": Exchange.SZSE,
    "BJ": Exchange.BSE,
}

EXCHANGE_TO_SUFFIX: dict[Exchange, str] = {
    Exchange.SSE: "SH",
    Exchange.SZSE: "SZ",
    Exchange.BSE: "BJ",
}


@dataclass
class StockItem:
    symbol: str
    exchange: Exchange
    name: str = ""

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    @property
    def tickflow_symbol(self) -> str:
        suffix = EXCHANGE_TO_SUFFIX.get(self.exchange, "")
        return f"{self.symbol}.{suffix}"

    @property
    def search_key(self) -> str:
        return f"{self.symbol} {self.name} {self.vt_symbol}".lower()


def parse_tickflow_symbol(tf_symbol: str, name: str = "") -> StockItem | None:
    if "." not in tf_symbol:
        return None
    code, suffix = tf_symbol.rsplit(".", 1)
    exchange = SUFFIX_TO_EXCHANGE.get(suffix.upper())
    if not exchange:
        return None
    return StockItem(symbol=code, exchange=exchange, name=name)
