"""TickFlow K 线分页拉取与 BarData 转换。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from tickflow import TickFlow
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData
from vnpy.trader.utility import round_to

from vnpy_tickflow.mapping import parse_datetime

MAX_BARS_PER_REQUEST = 10000


def fetch_klines_paged(
    client: TickFlow,
    tf_symbol: str,
    period: str,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """分页拉取 K 线并合并为单个 DataFrame。

    TickFlow 单次默认仅返回少量 K 线，需显式 count 并分页。
    """
    frames: list[pd.DataFrame] = []
    cursor_start = start_ms

    while cursor_start <= end_ms:
        df = client.klines.get(
            tf_symbol,
            period=period,
            start_time=cursor_start,
            end_time=end_ms,
            count=MAX_BARS_PER_REQUEST,
            adjust="forward",
            as_dataframe=True,
        )
        if df is None or df.empty:
            break

        frames.append(df)
        if len(df) < MAX_BARS_PER_REQUEST:
            break

        last_ts = int(df.iloc[-1]["timestamp"])
        if last_ts >= end_ms:
            break
        cursor_start = last_ts + 1

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["timestamp"], keep="last")


def parse_bar_datetime_from_row(row: pd.Series, interval: Interval) -> datetime | None:
    """从 DataFrame 行解析 K 线时间；无法解析时返回 None。"""
    if "trade_time" in row and pd.notna(row["trade_time"]):
        return parse_datetime(row["trade_time"], interval)
    if "timestamp" in row and pd.notna(row["timestamp"]):
        return parse_datetime(row["timestamp"], interval)
    if "trade_date" in row and pd.notna(row["trade_date"]):
        return parse_datetime(row["trade_date"], interval)
    return None


def _row_float(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if pd.isna(value):
        return default
    return float(value)


def dataframe_to_bars(
    df: pd.DataFrame,
    *,
    symbol: str,
    exchange: Exchange,
    interval: Interval,
    gateway_name: str = "TICKFLOW",
    sort: bool = True,
) -> list[BarData]:
    """将 TickFlow K 线 DataFrame 转为 VeighNa BarData 列表。"""
    if df is None or df.empty:
        return []

    bars: list[BarData] = []
    for _, row in df.iterrows():
        if pd.isna(row.get("open")):
            continue

        dt = parse_bar_datetime_from_row(row, interval)
        if dt is None:
            continue

        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                datetime=dt,
                open_price=round_to(float(row["open"]), 0.000001),
                high_price=round_to(_row_float(row, "high"), 0.000001),
                low_price=round_to(_row_float(row, "low"), 0.000001),
                close_price=round_to(_row_float(row, "close"), 0.000001),
                volume=_row_float(row, "volume"),
                turnover=_row_float(row, "amount"),
                open_interest=0,
                gateway_name=gateway_name,
            )
        )

    if sort:
        bars.sort(key=lambda item: item.datetime)
    return bars
