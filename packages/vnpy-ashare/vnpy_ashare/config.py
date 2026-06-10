"""A 股市场常量与回测默认参数。"""

from __future__ import annotations

import json
from pathlib import Path

from vnpy.trader.constant import Exchange, Interval

from vnpy_common.paths import VNTRADER_DIR

STOCK_EXCHANGES: frozenset[Exchange] = frozenset(
    {
        Exchange.SSE,
        Exchange.SZSE,
        Exchange.BSE,
    }
)

EXCHANGE_CN_NAMES: dict[Exchange, str] = {
    Exchange.SSE: "上交所",
    Exchange.SZSE: "深交所",
    Exchange.BSE: "北交所",
}

EXCHANGE_CN_SHORT: dict[Exchange, str] = {
    Exchange.SSE: "沪",
    Exchange.SZSE: "深",
    Exchange.BSE: "北",
}

_CN_NAME_TO_EXCHANGE: dict[str, Exchange] = {
    **{name: ex for ex, name in EXCHANGE_CN_NAMES.items()},
    **{short: ex for ex, short in EXCHANGE_CN_SHORT.items()},
    **{ex.value: ex for ex in STOCK_EXCHANGES},
}

LOT_SIZE: int = 100
PRICE_TICK: float = 0.01
COMMISSION_RATE: float = 0.0002
STAMP_TAX_RATE: float = 0.0005
# 万二双边佣金 + 万五印花税，折为 vnpy 单边 rate；用 round 避免 0.000449999… 浮点噪声
EFFECTIVE_RATE: float = round(
    (COMMISSION_RATE + COMMISSION_RATE + STAMP_TAX_RATE) / 2,
    6,
)


def format_decimal_field(value: float, *, places: int = 6) -> str:
    """回测表单小数展示，去掉二进制浮点尾数。"""
    text = f"{float(value):.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


BACKTESTER_SETTING_FILE = VNTRADER_DIR / "cta_backtester_setting.json"

ASHARE_BACKTEST_DEFAULTS: dict = {
    "class_name": "AshareDoubleMaStrategy",
    "vt_symbol": "600519.SSE",
    "interval": Interval.DAILY.value,
    "start": "2020-01-01",
    "rate": EFFECTIVE_RATE,
    "slippage": PRICE_TICK,
    "size": 1,
    "pricetick": PRICE_TICK,
    "capital": 100_000,
}


def exchange_to_cn(exchange: Exchange, *, short: bool = False) -> str:
    mapping = EXCHANGE_CN_SHORT if short else EXCHANGE_CN_NAMES
    return mapping.get(exchange, exchange.value)


def format_vt_symbol_cn(symbol: str, exchange: Exchange) -> str:
    return f"{symbol}.{exchange_to_cn(exchange)}"


def format_vt_symbol_str_cn(vt_symbol: str) -> str:
    if "." not in vt_symbol:
        return vt_symbol
    symbol, label = vt_symbol.rsplit(".", 1)
    exchange = _CN_NAME_TO_EXCHANGE.get(label)
    if exchange is None:
        try:
            exchange = Exchange(label)
        except ValueError:
            return vt_symbol
    return format_vt_symbol_cn(symbol, exchange)


def is_ashare_exchange(exchange: Exchange) -> bool:
    return exchange in STOCK_EXCHANGES


def normalize_volume(volume: int) -> int:
    lots = max(volume // LOT_SIZE, 1)
    return lots * LOT_SIZE


def write_backtest_defaults(path: Path | None = None) -> Path:
    target = path or BACKTESTER_SETTING_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        json.dump(ASHARE_BACKTEST_DEFAULTS, f, indent=4, ensure_ascii=False)
    return target


def _looks_like_futures_config(setting: dict) -> bool:
    vt_symbol = str(setting.get("vt_symbol", ""))
    futures_markers = ("CFFEX", "SHFE", "DCE", "CZCE", "INE", "GFEX", "888")
    if any(marker in vt_symbol for marker in futures_markers):
        return True
    try:
        return float(setting.get("size", 1)) > 1
    except (TypeError, ValueError):
        return False


def ensure_runtime_config(force: bool = False) -> bool:
    if force or not BACKTESTER_SETTING_FILE.exists():
        write_backtest_defaults()
        return True

    try:
        with BACKTESTER_SETTING_FILE.open(encoding="utf-8") as f:
            current = json.load(f)
    except (json.JSONDecodeError, OSError):
        write_backtest_defaults()
        return True

    if _looks_like_futures_config(current):
        write_backtest_defaults()
        return True

    return False
