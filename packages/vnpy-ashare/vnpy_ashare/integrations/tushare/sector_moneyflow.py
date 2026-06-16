"""板块级资金流向（东财行业/概念、同花顺概念）。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from vnpy_ashare.domain.calendar import last_trading_day, trading_days_between
from vnpy_ashare.domain.numbers import safe_float
from vnpy_ashare.domain.sector_flow import SectorFlowHistoryPoint, SectorFlowRow
from vnpy_ashare.integrations.tushare.cache import (
    DATASET_MONEYFLOW_CNT_THS,
    DATASET_MONEYFLOW_IND_DC,
    get_cached_rows,
    set_cached_rows,
)
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import _latest_trade_date_str

_DEFAULT_LOOKBACK_DAYS = 10
_HISTORY_FETCH_BUFFER_DAYS = 6
_LAST_SUCCESS_TRADE_DATE: dict[str, str] = {}


def recent_trading_date_strs(*, count: int) -> list[str]:
    """最近 count 个交易日（YYYYMMDD，新→旧）。"""
    need = max(1, count)
    end = last_trading_day()
    start = end - timedelta(days=max(need + _HISTORY_FETCH_BUFFER_DAYS, need * 3))
    open_days = trading_days_between(start, end)
    if not open_days:
        return [end.strftime("%Y%m%d")]
    return [day.strftime("%Y%m%d") for day in reversed(open_days[-(need + _HISTORY_FETCH_BUFFER_DAYS) :])]


def _match_sector_api_row(
    rows: list[dict[str, Any]],
    *,
    sector_id: str,
    sector_name: str,
) -> dict[str, Any] | None:
    sid = str(sector_id or "").strip()
    name = str(sector_name or "").strip()
    if sid:
        for row in rows:
            if str(row.get("ts_code") or "").strip() == sid:
                return row
    if name:
        for row in rows:
            if str(row.get("name") or "").strip() == name:
                return row
    return None


def _history_point_from_dc(row: dict[str, Any]) -> SectorFlowHistoryPoint:
    trade_date = str(row.get("trade_date") or "").strip()
    net_yi = float(row.get("net_amount") or 0) / 1e8
    return SectorFlowHistoryPoint(trade_date=trade_date, net_flow_yi=round(net_yi, 2))


def _history_point_from_ths(row: dict[str, Any]) -> SectorFlowHistoryPoint:
    trade_date = str(row.get("trade_date") or "").strip()
    net_yi = float(row.get("net_amount") or 0)
    return SectorFlowHistoryPoint(trade_date=trade_date, net_flow_yi=round(net_yi, 2))


def _use_ths_concept_api(sector: SectorFlowRow) -> bool:
    if sector.flow_source == "ths_concept":
        return True
    return sector.sector_kind == "concept" and str(sector.sector_id or "").endswith(".TI")


def fetch_sector_flow_history_from_tushare(
    sector: SectorFlowRow,
    *,
    limit: int = 5,
) -> list[SectorFlowHistoryPoint]:
    """从 Tushare 拉取单板块近 N 个交易日主力净流入。"""
    target = max(1, limit)
    points: list[SectorFlowHistoryPoint] = []
    seen_dates: set[str] = set()

    for trade_date in recent_trading_date_strs(count=target + _HISTORY_FETCH_BUFFER_DAYS):
        if len(points) >= target:
            break
        if trade_date in seen_dates:
            continue

        if _use_ths_concept_api(sector):
            rows, _ = fetch_moneyflow_cnt_ths(trade_date=trade_date)
            hit = _match_sector_api_row(rows, sector_id=sector.sector_id, sector_name=sector.name)
            if hit is None:
                continue
            point = _history_point_from_ths(hit)
        else:
            content_type = "概念" if sector.sector_kind == "concept" else "行业"
            rows, _ = fetch_moneyflow_ind_dc(trade_date=trade_date, content_type=content_type)
            hit = _match_sector_api_row(rows, sector_id=sector.sector_id, sector_name=sector.name)
            if hit is None:
                continue
            point = _history_point_from_dc(hit)

        if not point.trade_date or point.trade_date in seen_dates:
            continue
        seen_dates.add(point.trade_date)
        points.append(point)

    points.sort(key=lambda item: item.trade_date)
    return points[-target:]


def _trade_date_candidates(*, lookback_days: int) -> list[str]:
    end = last_trading_day()
    dates: list[str] = []
    for offset in range(lookback_days):
        day = end - timedelta(days=offset)
        if day.weekday() < 5:
            dates.append(day.strftime("%Y%m%d"))
    hinted = _LAST_SUCCESS_TRADE_DATE.get("sector_moneyflow")
    if hinted and hinted in dates:
        dates.remove(hinted)
        dates.insert(0, hinted)
    return dates


def fetch_moneyflow_ind_dc(
    *,
    trade_date: str | None = None,
    content_type: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """东财板块资金流向（行业/概念/地域）。"""
    trade_date = trade_date or _latest_trade_date_str()
    cache_key = trade_date if not content_type else f"{trade_date}:{content_type}"
    cached = get_cached_rows(DATASET_MONEYFLOW_IND_DC, cache_key)
    if cached is not None:
        return cached, trade_date

    try:
        pro = get_tushare_pro()
    except TushareNotConfiguredError:
        return [], trade_date

    params: dict[str, Any] = {
        "trade_date": trade_date,
        "fields": (
            "trade_date,content_type,ts_code,name,pct_change,close,net_amount,net_amount_rate,"
            "buy_sm_amount_stock,rank"
        ),
    }
    if content_type:
        params["content_type"] = content_type
    try:
        frame = pro.moneyflow_ind_dc(**params)
    except Exception:
        return [], trade_date
    if frame is None or frame.empty:
        return [], trade_date

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "trade_date": str(record.get("trade_date") or trade_date),
                "content_type": str(record.get("content_type") or content_type or "").strip(),
                "ts_code": str(record.get("ts_code") or "").strip(),
                "name": name,
                "pct_change": safe_float(record.get("pct_change")),
                "close": safe_float(record.get("close")),
                "net_amount": safe_float(record.get("net_amount")),
                "net_amount_rate": safe_float(record.get("net_amount_rate")),
                "leader_stock": str(record.get("buy_sm_amount_stock") or "").strip(),
                "rank": int(safe_float(record.get("rank")) or 0),
            }
        )
    if rows:
        set_cached_rows(DATASET_MONEYFLOW_IND_DC, cache_key, rows)
        _LAST_SUCCESS_TRADE_DATE["sector_moneyflow"] = trade_date
    return rows, trade_date


def fetch_moneyflow_cnt_ths(*, trade_date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """同花顺概念板块资金流向。"""
    trade_date = trade_date or _latest_trade_date_str()
    cached = get_cached_rows(DATASET_MONEYFLOW_CNT_THS, trade_date)
    if cached is not None:
        return cached, trade_date

    try:
        pro = get_tushare_pro()
    except TushareNotConfiguredError:
        return [], trade_date

    try:
        frame = pro.moneyflow_cnt_ths(
            trade_date=trade_date,
            fields=(
                "trade_date,ts_code,name,lead_stock,pct_change,company_num,"
                "pct_change_stock,net_buy_amount,net_sell_amount,net_amount"
            ),
        )
    except Exception:
        return [], trade_date
    if frame is None or frame.empty:
        return [], trade_date

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "trade_date": str(record.get("trade_date") or trade_date),
                "ts_code": str(record.get("ts_code") or "").strip(),
                "name": name,
                "leader_stock": str(record.get("lead_stock") or "").strip(),
                "pct_change": safe_float(record.get("pct_change")),
                "company_num": int(safe_float(record.get("company_num")) or 0),
                "leader_change_pct": safe_float(record.get("pct_change_stock")),
                "net_buy_amount": safe_float(record.get("net_buy_amount")),
                "net_sell_amount": safe_float(record.get("net_sell_amount")),
                "net_amount": safe_float(record.get("net_amount")),
            }
        )
    if rows:
        set_cached_rows(DATASET_MONEYFLOW_CNT_THS, trade_date, rows)
        _LAST_SUCCESS_TRADE_DATE["sector_moneyflow"] = trade_date
    return rows, trade_date


def fetch_moneyflow_ind_dc_with_fallback(
    *,
    content_type: str = "行业",
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> tuple[list[dict[str, Any]], str]:
    for trade_date in _trade_date_candidates(lookback_days=lookback_days):
        rows, resolved = fetch_moneyflow_ind_dc(trade_date=trade_date, content_type=content_type)
        if rows:
            return rows, resolved
    return [], ""


def fetch_moneyflow_cnt_ths_with_fallback(
    *,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> tuple[list[dict[str, Any]], str]:
    for trade_date in _trade_date_candidates(lookback_days=lookback_days):
        rows, resolved = fetch_moneyflow_cnt_ths(trade_date=trade_date)
        if rows:
            return rows, resolved
    return [], ""
