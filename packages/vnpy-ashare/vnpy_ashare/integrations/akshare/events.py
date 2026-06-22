"""AKShare 公告与新闻（东方财富等公开源）。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.time.china import china_now, format_china_date_compact


class AkshareNotInstalledError(ImportError):
    """未安装 akshare 可选依赖。"""


class AkshareFetchError(RuntimeError):
    """AKShare 拉取失败。"""


def _normalize_ann_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "—":
        return ""
    compact = text.replace("-", "").replace("/", "")[:8]
    return compact if len(compact) == 8 and compact.isdigit() else text


def _symbol_from_ts_code(ts_code: str) -> str:
    item = parse_stock_symbol(ts_code)
    if item is None:
        code = str(ts_code or "").split(".", 1)[0].strip()
        return code if code.isdigit() else ""
    return item.symbol


def fetch_announcements_akshare(
    ts_code: str,
    *,
    days: int = 180,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """拉取个股公告（东方财富公告大全）。"""
    ts_code = str(ts_code or "").strip()
    symbol = _symbol_from_ts_code(ts_code)
    if not symbol:
        return []

    try:
        import akshare as ak
    except ImportError as ex:
        raise AkshareNotInstalledError("未安装 akshare。请执行 `uv pip install akshare` 或安装 vnpy-ashare[events] 后重试。") from ex

    now = china_now()
    end = format_china_date_compact(now)
    start = format_china_date_compact(now - timedelta(days=max(days, 30)))

    try:
        frame = ak.stock_individual_notice_report(
            security=symbol,
            symbol="全部",
            begin_date=start,
            end_date=end,
        )
    except Exception as ex:
        raise AkshareFetchError(f"AKShare 公告拉取失败：{ex}") from ex

    if frame is None or frame.empty:
        return []

    rows = frame.to_dict(orient="records")
    rows.sort(key=lambda row: _normalize_ann_date(row.get("公告日期")), reverse=True)

    result: list[dict[str, Any]] = []
    for row in rows[:limit]:
        title = str(row.get("公告标题") or "").strip()
        if not title:
            continue
        ann_date = _normalize_ann_date(row.get("公告日期"))
        category = str(row.get("公告类型") or "").strip()
        payload: dict[str, Any] = {
            "ann_date": ann_date,
            "title": title,
            "url": str(row.get("网址") or "").strip(),
        }
        if category:
            payload["category"] = category
        result.append(payload)
    return result


def _normalize_pub_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isdigit() and len(text) >= 8:
        return text[:8]
    compact = text.replace("-", "").replace(":", "").replace(" ", "")[:14]
    if len(compact) >= 8 and compact[:8].isdigit():
        return compact[:8]
    return text


def fetch_stock_news_akshare(
    ts_code: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """拉取个股新闻（东方财富）。"""
    ts_code = str(ts_code or "").strip()
    symbol = _symbol_from_ts_code(ts_code)
    if not symbol:
        return []

    try:
        import akshare as ak
    except ImportError as ex:
        raise AkshareNotInstalledError("未安装 akshare。请执行 `uv pip install akshare` 或安装 vnpy-ashare[events] 后重试。") from ex

    try:
        frame = ak.stock_news_em(symbol=symbol)
    except Exception as ex:
        raise AkshareFetchError(f"AKShare 新闻拉取失败：{ex}") from ex

    if frame is None or frame.empty:
        return []

    rows = frame.to_dict(orient="records")
    rows.sort(key=lambda row: _normalize_pub_time(row.get("发布时间")), reverse=True)

    result: list[dict[str, Any]] = []
    for row in rows[:limit]:
        title = str(row.get("新闻标题") or "").strip()
        if not title:
            continue
        content = str(row.get("新闻内容") or "").strip()
        payload: dict[str, Any] = {
            "pub_time": _normalize_pub_time(row.get("发布时间")),
            "title": title,
            "source": str(row.get("文章来源") or "").strip(),
            "url": str(row.get("新闻链接") or "").strip(),
        }
        if content:
            payload["summary"] = content[:280]
        result.append(payload)
    return result
