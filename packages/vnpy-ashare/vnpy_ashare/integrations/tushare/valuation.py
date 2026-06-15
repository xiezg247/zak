"""Tushare 估值历史拉取。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from vnpy_ashare.integrations.tushare.client import get_tushare_pro


def fetch_valuation_history(
    ts_code: str,
    *,
    days: int = 750,
) -> list[dict[str, Any]]:
    """拉取单股 daily_basic 历史（PE/PB/市值等）。"""
    pro = get_tushare_pro()
    end = date.today()
    start = end - timedelta(days=max(days, 30))
    df = pro.daily_basic(
        ts_code=ts_code,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        fields=("ts_code,trade_date,close,pe_ttm,pb,total_mv,circ_mv,turnover_rate"),
    )
    if df is None or df.empty:
        return []
    return cast(list[dict[str, Any]], df.sort_values("trade_date").to_dict(orient="records"))
