"""同花顺概念板块（ths_index / ths_daily / ths_member）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.symbols import ts_code_to_vt_symbol
from vnpy_ashare.integrations.tushare.cache import (
    DATASET_THS_DAILY,
    DATASET_THS_INDEX,
    DATASET_THS_MEMBER,
    INDUSTRY_MAX_AGE,
    get_cached_rows,
    set_cached_rows,
)
from vnpy_ashare.integrations.tushare.client import get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import _latest_trade_date_str


def fetch_ths_concept_index_map() -> dict[str, str]:
    """概念指数 ts_code → 名称（type=N）。"""
    cached = get_cached_rows(DATASET_THS_INDEX, "", max_age=INDUSTRY_MAX_AGE)
    if cached is not None:
        return {str(item["ts_code"]): str(item["name"]) for item in cached if item.get("ts_code") and item.get("name")}

    pro = get_tushare_pro()
    try:
        frame = pro.ths_index(exchange="A", type="N", fields="ts_code,name,type")
    except Exception:
        return {}
    if frame is None or frame.empty:
        return {}

    rows: list[dict[str, Any]] = []
    mapping: dict[str, str] = {}
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code") or "").strip()
        name = str(record.get("name") or "").strip()
        if not ts_code or not name:
            continue
        rows.append({"ts_code": ts_code, "name": name, "type": str(record.get("type") or "")})
        mapping[ts_code] = name
    if rows:
        set_cached_rows(DATASET_THS_INDEX, "", rows)
    return mapping


def fetch_ths_daily_pct_map(trade_date: str | None = None) -> dict[str, float]:
    trade_date = trade_date or _latest_trade_date_str()
    cached = get_cached_rows(DATASET_THS_DAILY, trade_date)
    if cached is not None:
        return {str(item["ts_code"]): float(item.get("pct_chg") or 0) for item in cached if item.get("ts_code")}

    pro = get_tushare_pro()
    try:
        frame = pro.ths_daily(trade_date=trade_date, fields="ts_code,pct_chg")
    except Exception:
        return {}
    if frame is None or frame.empty:
        return {}

    rows: list[dict[str, Any]] = []
    pct_map: dict[str, float] = {}
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code") or "").strip()
        if not ts_code:
            continue
        pct = float(record.get("pct_chg") or 0)
        rows.append({"ts_code": ts_code, "pct_chg": pct})
        pct_map[ts_code] = pct
    if rows:
        set_cached_rows(DATASET_THS_DAILY, trade_date, rows)
    return pct_map


def fetch_ths_member_vt_symbols(concept_ts_code: str) -> list[str]:
    concept_ts_code = str(concept_ts_code or "").strip()
    if not concept_ts_code:
        return []
    cached = get_cached_rows(DATASET_THS_MEMBER, concept_ts_code, max_age=INDUSTRY_MAX_AGE)
    if cached is not None:
        return [str(item.get("vt_symbol") or "") for item in cached if item.get("vt_symbol")]

    pro = get_tushare_pro()
    try:
        frame = pro.ths_member(ts_code=concept_ts_code, fields="ts_code,con_code,name")
    except Exception:
        return []
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    vt_symbols: list[str] = []
    for record in frame.to_dict(orient="records"):
        con_code = str(record.get("con_code") or record.get("ts_code") or "").strip()
        vt_symbol = ts_code_to_vt_symbol(con_code)
        if not vt_symbol:
            continue
        rows.append({"vt_symbol": vt_symbol, "con_code": con_code})
        vt_symbols.append(vt_symbol)
    if rows:
        set_cached_rows(DATASET_THS_MEMBER, concept_ts_code, rows)
    return vt_symbols


def build_hot_concept_vt_symbol_map(*, top_concepts: int = 5) -> tuple[dict[str, str], list[str]]:
    """返回 vt_symbol → 主概念名、强势概念名列表。"""
    concept_map = fetch_ths_concept_index_map()
    if not concept_map:
        return {}, []

    pct_map = fetch_ths_daily_pct_map()
    ranked = sorted(
        [(code, pct_map.get(code, 0.0)) for code in concept_map],
        key=lambda item: item[1],
        reverse=True,
    )
    hot_names: list[str] = []
    vt_to_concept: dict[str, str] = {}
    for concept_code, _pct in ranked[:top_concepts]:
        name = concept_map.get(concept_code, "")
        if not name:
            continue
        hot_names.append(name)
        for vt_symbol in fetch_ths_member_vt_symbols(concept_code):
            if vt_symbol not in vt_to_concept:
                vt_to_concept[vt_symbol] = name
    return vt_to_concept, hot_names
