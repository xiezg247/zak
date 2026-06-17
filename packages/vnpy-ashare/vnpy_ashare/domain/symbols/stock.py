"""A 股标的符号体系：TickFlow / Tushare / VeighNa vt_symbol 互转与解析。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange
from vnpy.trader.utility import extract_vt_symbol
from pydantic import Field

from vnpy_ashare.domain.base import MutableModel

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

_VT_EXCHANGE_TO_SUFFIX: dict[str, str] = {
    "SSE": "SH",
    "SZSE": "SZ",
    "BSE": "BJ",
}


class StockItem(MutableModel):
    symbol: str = Field(description="六位股票代码")
    exchange: Exchange = Field(description="VeighNa 交易所枚举")
    name: str = Field(default="", description="证券简称")

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange.value}"

    @property
    def tickflow_symbol(self) -> str:
        suffix = EXCHANGE_TO_SUFFIX.get(self.exchange, "")
        return f"{self.symbol}.{suffix}"

    @property
    def ts_code(self) -> str:
        return symbol_exchange_to_ts_code(self.symbol, self.exchange)

    @property
    def search_key(self) -> str:
        return f"{self.symbol} {self.name} {self.vt_symbol}".lower()


def parse_tickflow_symbol(tf_symbol: str, name: str = "") -> StockItem | None:
    """TickFlow 符号（如 600519.SH）→ StockItem。"""
    if "." not in tf_symbol:
        return None
    code, suffix = tf_symbol.rsplit(".", 1)
    exchange = SUFFIX_TO_EXCHANGE.get(suffix.upper())
    if not exchange:
        return None
    return StockItem(symbol=code, exchange=exchange, name=name)


def parse_stock_symbol(symbol: str) -> StockItem | None:
    """
    解析 A 股代码，支持：
    - 600519.SSE / 600519.SZSE / 600519.BSE
    - 600519.SH / 600519.SZ / 600519.BJ
    - 600519（按首位推断交易所）
    """
    text = symbol.strip()
    if not text:
        return None

    if "." in text:
        code, suffix = text.rsplit(".", 1)
        suffix_upper = suffix.upper()
        if suffix_upper in SUFFIX_TO_EXCHANGE:
            return parse_tickflow_symbol(text)
        try:
            sym, exchange = extract_vt_symbol(text)
            return StockItem(symbol=sym, exchange=exchange)
        except ValueError:
            return None

    if len(text) == 6 and text.isdigit():
        if text.startswith(("5", "6", "9")):
            return StockItem(symbol=text, exchange=Exchange.SSE)
        if text.startswith(("0", "3")):
            return StockItem(symbol=text, exchange=Exchange.SZSE)
        if text.startswith(("4", "8")):
            return StockItem(symbol=text, exchange=Exchange.BSE)
    return None


def ts_code_to_vt_symbol(ts_code: str) -> str | None:
    """Tushare ts_code（如 000001.SZ）→ vt_symbol（000001.SZSE）。"""
    if "." not in ts_code:
        return None
    code, suffix = ts_code.rsplit(".", 1)
    exchange = SUFFIX_TO_EXCHANGE.get(suffix.upper())
    if not exchange:
        return None
    return f"{code}.{exchange.value}"


def vt_symbol_to_ts_code(vt_symbol: str) -> str | None:
    """vt_symbol → Tushare ts_code。"""
    if "." not in vt_symbol:
        return None
    code, exchange = vt_symbol.rsplit(".", 1)
    suffix = _VT_EXCHANGE_TO_SUFFIX.get(exchange.upper())
    if not suffix:
        return None
    return f"{code}.{suffix}"


def symbol_exchange_to_ts_code(symbol: str, exchange: Exchange) -> str:
    """A 股代码 + Exchange → Tushare ts_code。"""
    suffix = EXCHANGE_TO_SUFFIX.get(exchange)
    if suffix:
        return f"{symbol}.{suffix}"
    value = getattr(exchange, "value", str(exchange)).upper()
    if value in _VT_EXCHANGE_TO_SUFFIX:
        return f"{symbol}.{_VT_EXCHANGE_TO_SUFFIX[value]}"
    if symbol.startswith(("5", "6", "9")):
        return f"{symbol}.SH"
    if symbol.startswith(("0", "3")):
        return f"{symbol}.SZ"
    return f"{symbol}.BJ"


def symbol_exchange_to_tickflow(symbol: str, exchange: Exchange) -> str:
    """A 股代码 + Exchange → TickFlow 符号。"""
    suffix = EXCHANGE_TO_SUFFIX.get(exchange, "")
    return f"{symbol}.{suffix}" if suffix else symbol


def vt_symbol_to_symbol(vt_symbol: str) -> str:
    """vt_symbol / TickFlow 符号 → 六位代码。"""
    text = (vt_symbol or "").strip()
    if "." not in text:
        return text
    return text.rsplit(".", 1)[0]
