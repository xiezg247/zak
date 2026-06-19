"""Tushare 个股财报拉取（三表 + 财务指标）。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.domain.core.numbers import safe_float
from vnpy_ashare.integrations.tushare.client import get_tushare_pro

_MAINBZ_TYPES: tuple[tuple[str, str], ...] = (
    ("mainbz_p", "P"),
    ("mainbz_d", "D"),
)

_REPORT_APIS: dict[str, str] = {
    "income": "income",
    "balancesheet": "balancesheet",
    "cashflow": "cashflow",
    "fina_indicator": "fina_indicator",
    "express": "express",
    "forecast": "forecast",
}


def infer_period(end_date: str) -> str:
    """由报告期推断季度标签。"""
    text = str(end_date or "").strip()
    if len(text) < 8:
        return ""
    suffix = text[4:8]
    mapping = {
        "0331": "Q1",
        "0630": "H1",
        "0930": "Q3",
        "1231": "Annual",
    }
    return mapping.get(suffix, suffix)


def _frame_to_rows(frame) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        if not isinstance(record, dict):
            continue
        end_date = str(record.get("end_date") or record.get("end_dt") or "").strip()
        if not end_date:
            continue
        ann_date = str(record.get("ann_date") or record.get("f_ann_date") or "").strip()
        clean = {str(key): value for key, value in record.items() if value is not None}
        rows.append(
            {
                "end_date": end_date,
                "ann_date": ann_date,
                "period": infer_period(end_date),
                "fields": clean,
            }
        )
    rows.sort(key=lambda item: str(item["end_date"]), reverse=True)
    return rows


def fetch_financial_reports(
    ts_code: str,
    report_type: str,
    *,
    years: int = 5,
) -> list[dict[str, Any]]:
    """拉取单票指定类型财报行。"""
    api_name = _REPORT_APIS.get(report_type)
    if api_name is None:
        return []

    years = max(1, min(int(years or 5), 15))
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=years * 366)
    start_date = start_dt.strftime("%Y%m%d")
    end_date = end_dt.strftime("%Y%m%d")

    pro = get_tushare_pro()
    api = getattr(pro, api_name, None)
    if api is None:
        return []

    try:
        frame = api(ts_code=ts_code, start_date=start_date, end_date=end_date)
    except Exception:
        return []
    return _frame_to_rows(frame)


def _group_mainbz_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按报告期聚合 fina_mainbz 明细行。"""
    by_end: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in raw_rows:
        end_date = str(record.get("end_date") or "").strip()
        if not end_date:
            continue
        by_end[end_date].append(
            {
                "bz_item": str(record.get("bz_item") or "").strip(),
                "bz_sales": safe_float(record.get("bz_sales"), default=float("nan")),
                "bz_profit": safe_float(record.get("bz_profit"), default=float("nan")),
                "bz_cost": safe_float(record.get("bz_cost"), default=float("nan")),
                "bz_code": str(record.get("bz_code") or "").strip(),
            }
        )

    result: list[dict[str, Any]] = []
    for end_date, items in by_end.items():
        cleaned: list[dict[str, Any]] = []
        for item in items:
            row = dict(item)
            for key in ("bz_sales", "bz_profit", "bz_cost"):
                value = row.get(key)
                if isinstance(value, float) and value != value:
                    row[key] = None
            cleaned.append(row)
        cleaned.sort(key=lambda row: row.get("bz_sales") or 0, reverse=True)
        result.append(
            {
                "end_date": end_date,
                "ann_date": "",
                "period": infer_period(end_date),
                "fields": {"items": cleaned},
            }
        )
    result.sort(key=lambda row: str(row["end_date"]), reverse=True)
    return result


def fetch_mainbz_reports(
    ts_code: str,
    *,
    years: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """拉取主营业务构成（按产品 / 按地区）。"""
    years = max(1, min(int(years or 5), 15))
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=years * 366)
    start_date = start_dt.strftime("%Y%m%d")
    end_date = end_dt.strftime("%Y%m%d")

    pro = get_tushare_pro()
    api = getattr(pro, "fina_mainbz", None)
    if api is None:
        return {report_type: [] for report_type, _ in _MAINBZ_TYPES}

    result: dict[str, list[dict[str, Any]]] = {}
    for report_type, bz_type in _MAINBZ_TYPES:
        try:
            frame = api(ts_code=ts_code, type=bz_type, start_date=start_date, end_date=end_date)
        except Exception:
            result[report_type] = []
            continue
        raw_rows = []
        if frame is not None and not getattr(frame, "empty", True):
            raw_rows = frame.to_dict(orient="records")
        result[report_type] = _group_mainbz_rows(raw_rows)
    return result


def fetch_all_financial_reports(
    ts_code: str,
    *,
    years: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """拉取三表 + 财务指标 + 主营业务构成。"""
    result: dict[str, list[dict[str, Any]]] = {}
    for report_type in _REPORT_APIS:
        result[report_type] = fetch_financial_reports(ts_code, report_type, years=years)
    result.update(fetch_mainbz_reports(ts_code, years=years))
    return result


def field_float(fields: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in fields:
            continue
        value = safe_float(fields.get(key), default=float("nan"))
        if value != value:  # NaN
            continue
        return value
    return None
