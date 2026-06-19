"""Tushare 因子拉取与字段标准化。

符号互转见 ``domain.symbols``；``fetch_daily_basic`` / ``fetch_moneyflow`` 供 data_source 与选股规则使用。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.domain.core.numbers import safe_float
from vnpy_ashare.domain.market.indices import MARKET_INDEX_TS_CODES
from vnpy_ashare.domain.symbols.stock import EXCHANGE_TO_SUFFIX, ts_code_to_vt_symbol
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.integrations.tushare.cache import (
    DATASET_DAILY_BASIC,
    DATASET_INDEX_DAILY,
    DATASET_LIMIT_LIST,
    DATASET_MONEYFLOW,
    DATASET_MONEYFLOW_HSGT,
    DATASET_STOCK_BASIC,
    DATASET_STOCK_INDUSTRY,
    INDUSTRY_MAX_AGE,
    get_cached_industry_map,
    get_cached_pct_map,
    get_cached_rows,
    get_cached_stock_basic_industry_map,
    get_cached_sw_industry_map,
    merge_industry_maps,
    set_cached_industry_map,
    set_cached_pct_map,
    set_cached_rows,
)
from vnpy_ashare.integrations.tushare.client import get_tushare_pro
from vnpy_ashare.storage.repositories.universe import load_universe_rows


def fetch_daily_pct_map(trade_date: str) -> dict[str, float]:
    """拉取指定交易日全市场涨跌幅（供非交易时段涨幅榜）。"""
    cached = get_cached_pct_map(trade_date)
    if cached is not None:
        return cached

    pro = get_tushare_pro()
    try:
        frame = pro.daily(trade_date=trade_date, fields="ts_code,pct_chg")
    except Exception:
        return {}
    if frame is None or frame.empty:
        return {}
    pct_map = {str(record.get("ts_code", "")): safe_float(record.get("pct_chg")) for record in frame.to_dict(orient="records") if record.get("ts_code")}
    if pct_map:
        set_cached_pct_map(trade_date, pct_map)
    return pct_map


def load_ts_code_name_map() -> dict[str, str]:
    """从本地 universe 构建 ts_code → 证券名称映射。"""
    mapping: dict[str, str] = {}
    for symbol, exchange, name in load_universe_rows():
        suffix = EXCHANGE_TO_SUFFIX.get(exchange, "")
        if not suffix:
            continue
        mapping[f"{symbol}.{suffix}"] = name
    return mapping


def _latest_trade_date_str() -> str:
    return last_trading_day().strftime("%Y%m%d")


_INDEX_PREFETCH_CODES = MARKET_INDEX_TS_CODES
_INDEX_LOOKBACK_CALENDAR_DAYS = 120
_HSGT_LOOKBACK_CALENDAR_DAYS = 40


def fetch_stock_basic_snapshot(*, force: bool = False) -> tuple[list[dict[str, Any]], int]:
    """拉取上市标的基础信息（行业、板块、上市日期等）并写入缓存。"""
    if not force:
        cached = get_cached_rows(DATASET_STOCK_BASIC, "", max_age=INDUSTRY_MAX_AGE)
        if cached is not None:
            return cached, len(cached)

    pro = get_tushare_pro()
    try:
        frame = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name,industry,market,list_date,list_status,is_hs",
        )
    except Exception:
        return [], 0
    if frame is None or frame.empty:
        return [], 0

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", "")).strip()
        if not ts_code:
            continue
        rows.append(
            {
                "ts_code": ts_code,
                "name": str(record.get("name", "") or "").strip(),
                "industry": str(record.get("industry", "") or "").strip(),
                "market": str(record.get("market", "") or "").strip(),
                "list_date": str(record.get("list_date", "") or "").strip(),
                "list_status": str(record.get("list_status", "") or "").strip(),
                "is_hs": str(record.get("is_hs", "") or "").strip(),
            }
        )
    if rows:
        set_cached_rows(DATASET_STOCK_BASIC, "", rows)
        industry_map = {str(item["ts_code"]): str(item["industry"]) for item in rows if item.get("industry")}
        if industry_map:
            set_cached_industry_map(industry_map)
    return rows, len(rows)


def _load_stock_basic_industry_map() -> dict[str, str]:
    basic = get_cached_stock_basic_industry_map()
    if basic:
        return basic
    rows, _ = fetch_stock_basic_snapshot()
    if not rows:
        return {}
    return {str(item["ts_code"]): str(item["industry"]) for item in rows if item.get("industry")}


def _merge_with_stock_basic_industry(sw_mapping: dict[str, str]) -> dict[str, str]:
    basic = _load_stock_basic_industry_map()
    if basic:
        return merge_industry_maps(sw_mapping, basic)
    return sw_mapping


def fetch_stock_industry_map() -> dict[str, str]:
    """ts_code → 行业名称（优先申万 2021 L2，缺口回退 stock_basic.industry）。"""
    sw_mapping = get_cached_sw_industry_map()
    if sw_mapping:
        return _merge_with_stock_basic_industry(sw_mapping)

    from vnpy_ashare.integrations.tushare.sw_industry import fetch_sw_industry_map

    sw_mapping = fetch_sw_industry_map(force=False)
    if sw_mapping:
        return _merge_with_stock_basic_industry(sw_mapping)

    cached = get_cached_industry_map()
    if cached:
        return cached

    rows, _ = fetch_stock_basic_snapshot()
    if rows:
        return {str(item["ts_code"]): str(item["industry"]) for item in rows if item.get("industry")}

    pro = get_tushare_pro()
    try:
        frame = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,industry",
        )
    except Exception:
        return {}
    if frame is None or frame.empty:
        return {}
    mapping: dict[str, str] = {}
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", "")).strip()
        industry = str(record.get("industry", "") or "").strip()
        if ts_code and industry:
            mapping[ts_code] = industry
    if mapping:
        set_cached_industry_map(mapping)
    return mapping


def fetch_stock_industry_l1_map() -> dict[str, str]:
    """ts_code → 申万 2021 L1 行业名（无缓存时尝试从成分缓存推导）。"""
    from vnpy_ashare.integrations.tushare.cache import get_cached_sw_industry_l1_map
    from vnpy_ashare.integrations.tushare.sw_industry import fetch_sw_industry_l1_map

    cached = get_cached_sw_industry_l1_map()
    if cached:
        return cached
    return fetch_sw_industry_l1_map(force=False)


def fetch_industry_l2_to_l1_map() -> dict[str, str]:
    """申万 L2 名 → L1 名（供行业筛选分组）。"""
    from vnpy_ashare.integrations.tushare.sw_industry import fetch_l2_to_l1_map

    return fetch_l2_to_l1_map(force=False)


def fetch_sw_l2_index_map() -> dict[str, str]:
    """申万 L2 名 → index_code（行业板块唯一标识）。"""
    from vnpy_ashare.integrations.tushare.sw_industry import fetch_sw_l2_index_map as _fetch

    return _fetch(force=False)


def fetch_stock_market_board_map() -> dict[str, str]:
    """ts_code → 上市板块（stock_basic.market：主板/创业板/科创板等）。"""
    rows, _ = fetch_stock_basic_snapshot()
    if not rows:
        return {}
    return {str(item["ts_code"]): str(item["market"]) for item in rows if item.get("market")}


def fetch_limit_list_d(*, trade_date: str | None = None, limit_type: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """拉取涨跌停列表（limit_list_d）。"""
    trade_date = trade_date or _latest_trade_date_str()
    cache_key = trade_date if not limit_type else f"{trade_date}:{limit_type}"
    cached = get_cached_rows(DATASET_LIMIT_LIST, cache_key)
    if cached is not None:
        return cached, trade_date

    pro = get_tushare_pro()
    params: dict[str, Any] = {
        "trade_date": trade_date,
        "fields": "ts_code,trade_date,name,limit,limit_times,first_time,last_time,fd_amount,open_times,strth",
    }
    if limit_type:
        params["limit_type"] = limit_type
    try:
        frame = pro.limit_list_d(**params)
    except Exception:
        return [], trade_date
    if frame is None or frame.empty:
        return [], trade_date

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", "")).strip()
        if not ts_code:
            continue
        vt_symbol = ts_code_to_vt_symbol(ts_code)
        limit_times_raw = record.get("limit_times")
        limit_times = safe_float(limit_times_raw) if limit_times_raw not in (None, "") else 0.0
        fd_amount_raw = record.get("fd_amount")
        fd_amount = safe_float(fd_amount_raw) if fd_amount_raw not in (None, "") else None
        open_times_raw = record.get("open_times")
        open_times: int | None = None
        if open_times_raw not in (None, ""):
            try:
                open_times = int(float(open_times_raw))
            except (TypeError, ValueError):
                open_times = None
        strth_raw = record.get("strth")
        strth = safe_float(strth_raw) if strth_raw not in (None, "") else None
        rows.append(
            {
                "ts_code": ts_code,
                "trade_date": str(record.get("trade_date", trade_date)),
                "name": str(record.get("name", "") or "").strip(),
                "limit": str(record.get("limit", "") or "").strip(),
                "limit_times": limit_times,
                "first_time": str(record.get("first_time", "") or "").strip(),
                "last_time": str(record.get("last_time", "") or "").strip(),
                "fd_amount": fd_amount,
                "open_times": open_times,
                "strth": strth,
                "vt_symbol": vt_symbol or "",
            }
        )
    if rows:
        set_cached_rows(DATASET_LIMIT_LIST, cache_key, rows)
    return rows, trade_date


def fetch_index_daily_snapshot(*, trade_date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """拉取主要指数近期日线（供恐贪指数等复用）。"""
    trade_date = trade_date or _latest_trade_date_str()
    cached = get_cached_rows(DATASET_INDEX_DAILY, trade_date)
    if cached is not None:
        return cached, trade_date

    end_dt = datetime.strptime(trade_date, "%Y%m%d")
    start_date = (end_dt - timedelta(days=_INDEX_LOOKBACK_CALENDAR_DAYS)).strftime("%Y%m%d")

    pro = get_tushare_pro()
    rows: list[dict[str, Any]] = []
    for ts_code in _INDEX_PREFETCH_CODES:
        try:
            frame = pro.index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=trade_date,
                fields="ts_code,trade_date,close,pct_chg,amount",
            )
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        for record in frame.to_dict(orient="records"):
            rows.append(
                {
                    "ts_code": str(record.get("ts_code", ts_code)),
                    "trade_date": str(record.get("trade_date", "")),
                    "close": safe_float(record.get("close")),
                    "pct_chg": safe_float(record.get("pct_chg")),
                    "amount": safe_float(record.get("amount")),
                }
            )
    if rows:
        set_cached_rows(DATASET_INDEX_DAILY, trade_date, rows)
    return rows, trade_date


def fetch_moneyflow_hsgt_window(*, trade_date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """拉取沪深港通资金流近期窗口。"""
    trade_date = trade_date or _latest_trade_date_str()
    cached = get_cached_rows(DATASET_MONEYFLOW_HSGT, trade_date)
    if cached is not None:
        return cached, trade_date

    end_dt = datetime.strptime(trade_date, "%Y%m%d")
    start_date = (end_dt - timedelta(days=_HSGT_LOOKBACK_CALENDAR_DAYS)).strftime("%Y%m%d")

    pro = get_tushare_pro()
    try:
        frame = pro.moneyflow_hsgt(
            start_date=start_date,
            end_date=trade_date,
            fields="trade_date,north_money,south_money",
        )
    except Exception:
        return [], trade_date
    if frame is None or frame.empty:
        return [], trade_date

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        rows.append(
            {
                "trade_date": str(record.get("trade_date", "")),
                "north_money": safe_float(record.get("north_money")),
                "south_money": safe_float(record.get("south_money")),
            }
        )
    if rows:
        set_cached_rows(DATASET_MONEYFLOW_HSGT, trade_date, rows)
    return rows, trade_date


def fetch_daily_basic(*, trade_date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """拉取 daily_basic 并标准化为选股行（含 vt_symbol / pe_ttm / total_mv 等）。"""
    trade_date = trade_date or _latest_trade_date_str()
    cached = get_cached_rows(DATASET_DAILY_BASIC, trade_date)
    if cached is not None:
        return cached, trade_date

    pro = get_tushare_pro()
    frame = pro.daily_basic(
        trade_date=trade_date,
        fields=("ts_code,trade_date,close,pe,pe_ttm,pb,ps,total_mv,circ_mv,turnover_rate,volume_ratio"),
    )
    if frame is None or frame.empty:
        return [], trade_date

    names = load_ts_code_name_map()
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", ""))
        vt_symbol = ts_code_to_vt_symbol(ts_code)
        if not vt_symbol:
            continue
        symbol = vt_symbol.split(".", 1)[0]
        rows.append(
            {
                "ts_code": ts_code,
                "symbol": symbol,
                "name": names.get(ts_code, ""),
                "vt_symbol": vt_symbol,
                "trade_date": str(record.get("trade_date", trade_date)),
                "close": safe_float(record.get("close")),
                "pe": safe_float(record.get("pe")),
                "pe_ttm": safe_float(record.get("pe_ttm")),
                "pb": safe_float(record.get("pb")),
                "ps": safe_float(record.get("ps")),
                "total_mv": safe_float(record.get("total_mv")),
                "circ_mv": safe_float(record.get("circ_mv")),
                "turnover_rate": safe_float(record.get("turnover_rate")),
                "volume_ratio": safe_float(record.get("volume_ratio")),
            }
        )
    if rows:
        set_cached_rows(DATASET_DAILY_BASIC, trade_date, rows)
    return rows, trade_date


def fetch_moneyflow(*, trade_date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """拉取 moneyflow 并标准化为选股行（含 net_mf_amount 等）。"""
    trade_date = trade_date or _latest_trade_date_str()
    cached = get_cached_rows(DATASET_MONEYFLOW, trade_date)
    if cached is not None:
        return cached, trade_date

    pro = get_tushare_pro()
    frame = pro.moneyflow(
        trade_date=trade_date,
        fields=("ts_code,trade_date,net_mf_amount,buy_elg_amount,sell_elg_amount,buy_lg_amount,sell_lg_amount,buy_md_amount,sell_md_amount"),
    )
    if frame is None or frame.empty:
        return [], trade_date

    names = load_ts_code_name_map()
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", ""))
        vt_symbol = ts_code_to_vt_symbol(ts_code)
        if not vt_symbol:
            continue
        symbol = vt_symbol.split(".", 1)[0]
        rows.append(
            {
                "ts_code": ts_code,
                "symbol": symbol,
                "name": names.get(ts_code, ""),
                "vt_symbol": vt_symbol,
                "trade_date": str(record.get("trade_date", trade_date)),
                "net_mf_amount": safe_float(record.get("net_mf_amount")),
                "buy_elg_amount": safe_float(record.get("buy_elg_amount")),
                "sell_elg_amount": safe_float(record.get("sell_elg_amount")),
                "buy_lg_amount": safe_float(record.get("buy_lg_amount")),
                "sell_lg_amount": safe_float(record.get("sell_lg_amount")),
                "buy_md_amount": safe_float(record.get("buy_md_amount")),
                "sell_md_amount": safe_float(record.get("sell_md_amount")),
                "moneyflow_source": "tushare",
            }
        )
    if rows:
        set_cached_rows(DATASET_MONEYFLOW, trade_date, rows)
    return rows, trade_date
