"""个股事件日历：披露、分红、解禁、公告。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.corporate import (
    fetch_announcements,
    fetch_dividends,
    fetch_share_float,
)
from vnpy_ashare.integrations.tushare.disclosure import fetch_disclosure_dates
from vnpy_ashare.services.stock.profile import sync_disclosure_calendar
from vnpy_ashare.storage.repositories.disclosure import list_disclosure_calendar, upsert_disclosure_rows


@dataclass
class EventsProfile:
    ts_code: str
    vt_symbol: str
    disclosure: list[dict[str, str]] = field(default_factory=list)
    dividends: list[dict[str, Any]] = field(default_factory=list)
    share_float: list[dict[str, Any]] = field(default_factory=list)
    announcements: list[dict[str, Any]] = field(default_factory=list)
    upcoming_hints: list[str] = field(default_factory=list)
    message: str = ""


def _parse_yyyymmdd(text: str) -> datetime | None:
    value = str(text or "").strip()
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return None


def _build_upcoming_hints(profile: EventsProfile) -> list[str]:
    hints: list[str] = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = today + timedelta(days=30)

    for row in profile.disclosure:
        for key, label in (("ann_date", "披露"), ("pre_date", "预约披露")):
            dt = _parse_yyyymmdd(str(row.get(key) or ""))
            if dt is None or dt < today or dt > horizon:
                continue
            days = (dt - today).days
            hints.append(f"{days} 天后{label}（报告期 {row.get('end_date', '—')}）")
            break

    for row in profile.share_float:
        dt = _parse_yyyymmdd(str(row.get("float_date") or ""))
        if dt is None or dt < today or dt > horizon:
            continue
        ratio = row.get("float_ratio")
        ratio_text = f"{ratio:.2f}%" if isinstance(ratio, (int, float)) else "—"
        days = (dt - today).days
        hints.append(f"{days} 天后解禁 {ratio_text}（{row.get('holder_name') or '—'}）")

    for row in profile.dividends:
        dt = _parse_yyyymmdd(str(row.get("ex_date") or ""))
        if dt is None or dt < today or dt > horizon:
            continue
        cash = row.get("cash_div")
        cash_text = f"{cash:.4f} 元/股" if isinstance(cash, (int, float)) else ""
        days = (dt - today).days
        hints.append(f"{days} 天后除权除息 {cash_text}".strip())

    return hints[:5]


def build_events_profile(vt_symbol: str, *, sync_disclosure: bool = True) -> EventsProfile:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return EventsProfile(ts_code="", vt_symbol=vt_symbol, message="无法解析代码")

    ts_code = item.ts_code
    message = ""

    if sync_disclosure:
        sync_disclosure_calendar(vt_symbol)

    disclosure_rows = list_disclosure_calendar(ts_code, limit=6)
    if not disclosure_rows:
        try:
            remote = fetch_disclosure_dates(ts_code)
            if remote:
                upsert_disclosure_rows(ts_code, remote)
                disclosure_rows = list_disclosure_calendar(ts_code, limit=6)
        except TushareNotConfiguredError as ex:
            message = str(ex)
        except Exception:
            pass

    disclosure = [
        {
            "end_date": row.end_date,
            "pre_date": row.pre_date,
            "ann_date": row.ann_date,
            "actual_date": row.actual_date,
        }
        for row in disclosure_rows
    ]

    dividends: list[dict[str, Any]] = []
    share_float: list[dict[str, Any]] = []
    announcements: list[dict[str, Any]] = []
    try:
        dividends = fetch_dividends(ts_code)
        share_float = fetch_share_float(ts_code)
        announcements = fetch_announcements(ts_code)
    except TushareNotConfiguredError as ex:
        if not message:
            message = str(ex)
    except Exception as ex:
        message = str(ex)

    profile = EventsProfile(
        ts_code=ts_code,
        vt_symbol=item.vt_symbol,
        disclosure=disclosure,
        dividends=dividends,
        share_float=share_float,
        announcements=announcements,
        message=message,
    )
    profile.upcoming_hints = _build_upcoming_hints(profile)
    if not message and not (profile.disclosure or profile.dividends or profile.share_float or profile.announcements):
        profile.message = "暂无事件数据"
    return profile
