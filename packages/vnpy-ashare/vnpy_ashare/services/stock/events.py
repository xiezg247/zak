"""个股事件日历：披露、分红、解禁、公告。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.stock.events import EventsProfile
from vnpy_ashare.integrations.events.announcements import AnnouncementFetchError, fetch_announcements
from vnpy_ashare.integrations.events.news import NewsFetchError, fetch_stock_news
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.corporate import fetch_dividends, fetch_share_float
from vnpy_ashare.integrations.tushare.disclosure import fetch_disclosure_dates
from vnpy_ashare.services.stock.profile import sync_disclosure_calendar
from vnpy_ashare.storage.repositories.disclosure import list_disclosure_calendar, upsert_disclosure_rows

_EVENT_API_TIMEOUT = 8.0


def _call_with_timeout(fn, *args, **kwargs):
    """在独立线程中执行函数，超时返回 None。"""
    import concurrent.futures as cf

    executor = cf.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fn, *args, **kwargs)
        return future.result(timeout=_EVENT_API_TIMEOUT)
    except (cf.TimeoutError, TimeoutError):
        return None
    finally:
        executor.shutdown(wait=False)


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


def build_disclosure_upcoming_hints(ts_code: str, *, limit: int = 6) -> list[str]:
    """基于本地披露日历生成近 30 日事件提示（概览仪表盘用）。"""
    rows = list_disclosure_calendar(ts_code, limit=limit)
    if not rows:
        return []
    profile = EventsProfile(
        ts_code=ts_code,
        vt_symbol="",
        disclosure=[
            {
                "end_date": row.end_date,
                "pre_date": row.pre_date,
                "ann_date": row.ann_date,
            }
            for row in rows
        ],
    )
    return _build_upcoming_hints(profile)


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
    news: list[dict[str, Any]] = []
    extra_messages: list[str] = []
    try:
        dividends = _call_with_timeout(fetch_dividends, ts_code) or []
    except TushareNotConfiguredError as ex:
        extra_messages.append(str(ex))
    except Exception as ex:
        extra_messages.append(str(ex))

    try:
        share_float = _call_with_timeout(fetch_share_float, ts_code) or []
    except TushareNotConfiguredError as ex:
        extra_messages.append(str(ex))
    except Exception as ex:
        extra_messages.append(str(ex))

    try:
        announcements = _call_with_timeout(fetch_announcements, ts_code) or []
    except AnnouncementFetchError as ex:
        extra_messages.append(str(ex))

    try:
        news = _call_with_timeout(fetch_stock_news, ts_code) or []
    except NewsFetchError as ex:
        extra_messages.append(str(ex))

    if extra_messages:
        joined = "；".join(extra_messages)
        message = f"{message}；{joined}" if message else joined

    profile = EventsProfile(
        ts_code=ts_code,
        vt_symbol=item.vt_symbol,
        disclosure=disclosure,
        dividends=dividends,
        share_float=share_float,
        announcements=announcements,
        news=news,
        message=message,
    )
    profile.upcoming_hints = _build_upcoming_hints(profile)
    if not message and not (profile.disclosure or profile.dividends or profile.share_float or profile.announcements or profile.news):
        profile.message = "暂无事件数据"
    return profile
