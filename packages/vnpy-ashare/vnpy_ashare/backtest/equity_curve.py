"""回测权益曲线采样（供 AI 迷你图）。"""

from __future__ import annotations

from typing import Any

from pandas import DataFrame


def sample_equity_curve(df: DataFrame | None, *, max_points: int = 60) -> list[dict[str, Any]]:
    """从回测 result_df 均匀采样 balance 序列。"""
    if df is None or df.empty or "balance" not in df.columns:
        return []

    frame = df[["balance"]].dropna()
    if frame.empty:
        return []

    limit = max(2, min(int(max_points or 60), 120))
    if len(frame) <= limit:
        indices = list(range(len(frame)))
    else:
        step = (len(frame) - 1) / (limit - 1)
        indices = sorted({int(round(step * offset)) for offset in range(limit)})
        indices[0] = 0
        indices[-1] = len(frame) - 1

    rows: list[dict[str, Any]] = []
    for index in indices:
        ts = frame.index[index]
        if hasattr(ts, "strftime"):
            date = ts.strftime("%Y-%m-%d")
        else:
            date = str(ts)[:10]
        try:
            value = round(float(frame.iloc[index, 0]), 2)
        except (TypeError, ValueError):
            continue
        rows.append({"date": date, "value": value})
    return rows
