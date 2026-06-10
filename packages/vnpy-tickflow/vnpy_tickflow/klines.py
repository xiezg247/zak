"""TickFlow K 线分页拉取。"""

from __future__ import annotations

import pandas as pd
from tickflow import TickFlow

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
