"""上市公司公告：AKShare 主源，Tushare anns_d 可选回退。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from vnpy_ashare.domain.time.china import china_now, format_china_date_compact
from vnpy_ashare.integrations.akshare.events import (
    AkshareFetchError,
    AkshareNotInstalledError,
    fetch_announcements_akshare,
)
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro


class AnnouncementFetchError(RuntimeError):
    """所有公告数据源均不可用。"""


def _records(frame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return cast(list[dict[str, Any]], frame.to_dict(orient="records"))


def _fetch_announcements_tushare(
    ts_code: str,
    *,
    days: int,
    limit: int,
) -> list[dict[str, Any]] | None:
    """Tushare anns_d；无权限或接口错误时返回 None。"""
    now = china_now()
    end = format_china_date_compact(now)
    start = format_china_date_compact(now - timedelta(days=max(days, 30)))
    try:
        pro = get_tushare_pro()
        frame = pro.anns_d(ts_code=ts_code, start_date=start, end_date=end)
    except TushareNotConfiguredError:
        return None
    except Exception:
        return None

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


def fetch_announcements(ts_code: str, *, days: int = 180, limit: int = 20) -> list[dict[str, Any]]:
    """拉取个股公告；优先 AKShare，失败时尝试 Tushare anns_d。"""
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []

    errors: list[str] = []
    try:
        rows = fetch_announcements_akshare(ts_code, days=days, limit=limit)
        return rows
    except AkshareNotInstalledError as ex:
        errors.append(str(ex))
    except AkshareFetchError as ex:
        errors.append(str(ex))

    fallback = _fetch_announcements_tushare(ts_code, days=days, limit=limit)
    if fallback is not None:
        return fallback

    if errors:
        raise AnnouncementFetchError("；".join(errors))
    raise AnnouncementFetchError("公告数据源不可用（AKShare 失败且 Tushare anns_d 无权限或未配置）。")
