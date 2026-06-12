"""Tushare 概念板块。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro


def fetch_stock_concepts(ts_code: str) -> list[dict[str, Any]]:
    """拉取单票所属概念（concept_detail）。"""
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []
    try:
        pro = get_tushare_pro()
    except TushareNotConfiguredError:
        return []

    try:
        frame = pro.concept_detail(ts_code=ts_code, fields="id,concept_name,ts_code,name")
    except Exception:
        return []
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        concept_name = str(record.get("concept_name") or "").strip()
        if not concept_name:
            continue
        rows.append(
            {
                "concept_id": str(record.get("id") or ""),
                "concept_name": concept_name,
            }
        )
    rows.sort(key=lambda item: item["concept_name"])
    return rows
