"""Tushare 财报披露计划。"""

from __future__ import annotations

from typing import Any, cast

from vnpy_ashare.integrations.tushare.client import get_tushare_pro


def fetch_disclosure_dates(ts_code: str) -> list[dict[str, Any]]:
    pro = get_tushare_pro()
    df = pro.disclosure_date(ts_code=ts_code)
    if df is None or df.empty:
        return []
    return cast(list[dict[str, Any]], df.sort_values("end_date", ascending=False).to_dict(orient="records"))
