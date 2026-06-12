"""Tushare 股东、分红、解禁与公告。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.domain.numbers import safe_float
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro


def _records(frame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return frame.to_dict(orient="records")


def fetch_top10_holders(ts_code: str, *, limit: int = 10) -> list[dict[str, Any]]:
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []
    try:
        pro = get_tushare_pro()
        frame = pro.top10_holders(
            ts_code=ts_code,
            fields="ts_code,ann_date,end_date,holder_name,hold_amount,hold_ratio",
        )
    except TushareNotConfiguredError:
        raise
    except Exception:
        return []

    rows = _records(frame)
    if not rows:
        return []

    latest_end = max(str(row.get("end_date") or "") for row in rows)
    filtered = [row for row in rows if str(row.get("end_date") or "") == latest_end]
    filtered.sort(key=lambda row: safe_float(row.get("hold_ratio")) or 0, reverse=True)
    result: list[dict[str, Any]] = []
    for row in filtered[:limit]:
        result.append(
            {
                "end_date": str(row.get("end_date") or ""),
                "ann_date": str(row.get("ann_date") or ""),
                "holder_name": str(row.get("holder_name") or ""),
                "hold_amount": safe_float(row.get("hold_amount")),
                "hold_ratio": safe_float(row.get("hold_ratio")),
            }
        )
    return result


def fetch_dividends(ts_code: str, *, limit: int = 8) -> list[dict[str, Any]]:
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []
    try:
        pro = get_tushare_pro()
        frame = pro.dividend(
            ts_code=ts_code,
            fields="ts_code,end_date,ann_date,div_proc,stk_div,cash_div,record_date,ex_date,pay_date",
        )
    except TushareNotConfiguredError:
        raise
    except Exception:
        return []

    rows = _records(frame)
    rows.sort(key=lambda row: str(row.get("end_date") or ""), reverse=True)
    result: list[dict[str, Any]] = []
    for row in rows[:limit]:
        result.append(
            {
                "end_date": str(row.get("end_date") or ""),
                "ann_date": str(row.get("ann_date") or ""),
                "div_proc": str(row.get("div_proc") or ""),
                "stk_div": safe_float(row.get("stk_div")),
                "cash_div": safe_float(row.get("cash_div")),
                "ex_date": str(row.get("ex_date") or ""),
                "pay_date": str(row.get("pay_date") or ""),
            }
        )
    return result


def fetch_share_float(ts_code: str, *, limit: int = 8) -> list[dict[str, Any]]:
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []
    try:
        pro = get_tushare_pro()
        frame = pro.share_float(
            ts_code=ts_code,
            fields="ts_code,ann_date,float_date,float_share,float_ratio,holder_name,share_type",
        )
    except TushareNotConfiguredError:
        raise
    except Exception:
        return []

    rows = _records(frame)
    rows.sort(key=lambda row: str(row.get("float_date") or ""), reverse=True)
    result: list[dict[str, Any]] = []
    for row in rows[:limit]:
        result.append(
            {
                "ann_date": str(row.get("ann_date") or ""),
                "float_date": str(row.get("float_date") or ""),
                "float_share": safe_float(row.get("float_share")),
                "float_ratio": safe_float(row.get("float_ratio")),
                "holder_name": str(row.get("holder_name") or ""),
                "share_type": str(row.get("share_type") or ""),
            }
        )
    return result


def fetch_announcements(ts_code: str, *, days: int = 180, limit: int = 20) -> list[dict[str, Any]]:
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=max(days, 30))).strftime("%Y%m%d")
    try:
        pro = get_tushare_pro()
        frame = pro.anns(
            ts_code=ts_code,
            start_date=start,
            end_date=end,
            fields="ts_code,ann_date,name,title,url",
        )
    except TushareNotConfiguredError:
        raise
    except Exception:
        return []

    rows = _records(frame)
    rows.sort(key=lambda row: str(row.get("ann_date") or ""), reverse=True)
    result: list[dict[str, Any]] = []
    for row in rows[:limit]:
        title = str(row.get("title") or row.get("name") or "").strip()
        if not title:
            continue
        result.append(
            {
                "ann_date": str(row.get("ann_date") or ""),
                "title": title,
                "url": str(row.get("url") or ""),
            }
        )
    return result
