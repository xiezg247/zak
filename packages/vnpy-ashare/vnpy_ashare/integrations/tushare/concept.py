"""Tushare 概念板块。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.concept_board import fetch_ths_concept_index_map


def _fetch_stock_concepts_ths(ts_code: str) -> list[dict[str, Any]]:
    """通过同花顺 ths_member(con_code) 反查所属概念。"""
    pro = get_tushare_pro()
    try:
        frame = pro.ths_member(con_code=ts_code, fields="ts_code,con_code")
    except Exception:
        return []
    if frame is None or frame.empty:
        return []

    concept_map = fetch_ths_concept_index_map()
    if not concept_map:
        return []

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in frame.to_dict(orient="records"):
        concept_code = str(record.get("ts_code") or "").strip()
        if not concept_code or concept_code in seen:
            continue
        concept_name = concept_map.get(concept_code)
        if not concept_name:
            continue
        seen.add(concept_code)
        rows.append({"concept_id": concept_code, "concept_name": concept_name})
    rows.sort(key=lambda item: item["concept_name"])
    return rows


def _fetch_stock_concepts_legacy(ts_code: str) -> list[dict[str, Any]]:
    """旧版 concept_detail 反查（积分要求较低，作兜底）。"""
    pro = get_tushare_pro()
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


def fetch_stock_concepts(ts_code: str) -> list[dict[str, Any]]:
    """拉取单票所属概念（优先 ths_member，兜底 concept_detail）。"""
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []
    try:
        get_tushare_pro()
    except TushareNotConfiguredError:
        raise

    rows = _fetch_stock_concepts_ths(ts_code)
    if rows:
        return rows
    return _fetch_stock_concepts_legacy(ts_code)
