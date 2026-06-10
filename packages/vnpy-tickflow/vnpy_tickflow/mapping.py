"""TickFlow ↔ VeighNa 映射与常量。"""

from __future__ import annotations

from datetime import datetime, timedelta

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.utility import ZoneInfo

CHINA_TZ = ZoneInfo("Asia/Shanghai")

# 本项目聚焦 A 股，其他市场仅作扩展保留
ASHARE_EXCHANGES = frozenset({Exchange.SSE, Exchange.SZSE, Exchange.BSE})

EXCHANGE_VT2TF: dict[Exchange, str] = {
    Exchange.SSE: "SH",
    Exchange.SZSE: "SZ",
    Exchange.BSE: "BJ",
    Exchange.SHFE: "SHF",
    Exchange.DCE: "DCE",
    Exchange.CZCE: "ZCE",
    Exchange.CFFEX: "CFX",
    Exchange.INE: "INE",
    Exchange.GFEX: "GFE",
    Exchange.SEHK: "HK",
    Exchange.NASDAQ: "US",
    Exchange.NYSE: "US",
    Exchange.AMEX: "US",
}

INTERVAL_VT2TF: dict[Interval, str] = {
    Interval.MINUTE: "1m",
    Interval.HOUR: "60m",
    Interval.DAILY: "1d",
    Interval.WEEKLY: "1w",
}

INTERVAL_ADJUSTMENT_MAP: dict[Interval, timedelta] = {
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(),
    Interval.WEEKLY: timedelta(),
}

FREE_PERIODS = frozenset({"1d", "1w", "1M", "1Q", "1Y"})


def to_tf_symbol(symbol: str, exchange: Exchange) -> str | None:
    """将 VeighNa 合约代码转换为 TickFlow 代码格式。"""
    suffix = EXCHANGE_VT2TF.get(exchange)
    if not suffix:
        return None
    return f"{symbol}.{suffix}"


def interval_to_period(interval: Interval) -> str | None:
    return INTERVAL_VT2TF.get(interval)


def parse_datetime(value: str | int | float, interval: Interval) -> datetime:
    """解析 TickFlow 返回的时间字段。"""
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value / 1000, tz=CHINA_TZ)
    else:
        text = str(value)
        if len(text) == 8:
            dt = datetime.strptime(text, "%Y%m%d")
        elif " " in text:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(text, "%Y-%m-%d")
        dt = dt.replace(tzinfo=CHINA_TZ)

    adjustment = INTERVAL_ADJUSTMENT_MAP.get(interval, timedelta())
    return dt - adjustment
