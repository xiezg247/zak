"""个股板块、估值与披露计划。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.disclosure import fetch_disclosure_dates
from vnpy_ashare.integrations.tushare.factors import (
    fetch_daily_pct_map,
    fetch_stock_industry_map,
)
from vnpy_ashare.integrations.tushare.valuation import fetch_valuation_history
from vnpy_ashare.screener.data.data_source import fetch_daily_basic_with_fallback
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution
from vnpy_ashare.storage.repositories.disclosure import (
    list_disclosure_calendar,
    upsert_disclosure_rows,
)
from vnpy_ashare.storage.repositories.valuation import (
    latest_valuation_trade_date,
    list_valuation_history,
    upsert_valuation_rows,
)
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows

_VALUATION_TTL_DAYS = 7
_PEER_TOP_N = 10


@dataclass
class ValuationProfile:
    ts_code: str
    vt_symbol: str
    trade_date: str = ""
    pe_ttm: float | None = None
    pb: float | None = None
    total_mv: float | None = None
    circ_mv: float | None = None
    pe_percentile_3y: float | None = None
    pb_percentile_3y: float | None = None
    history_days: int = 0
    synced: bool = False
    message: str = ""


@dataclass
class SectorProfile:
    ts_code: str
    vt_symbol: str
    name: str
    industry: str = ""
    trade_date: str = ""
    sector_count: int = 0
    sector_avg_change_pct: float | None = None
    sector_rank: int | None = None
    peers: list[dict[str, Any]] = field(default_factory=list)
    disclosure: list[dict[str, str]] = field(default_factory=list)


def _percentile_rank(values: list[float], current: float | None) -> float | None:
    if current is None or current <= 0:
        return None
    sample = sorted(value for value in values if value is not None and value > 0)
    if not sample:
        return None
    below = sum(1 for value in sample if value <= current)
    return round(below / len(sample) * 100, 1)


def _valuation_needs_sync(ts_code: str, *, force: bool) -> bool:
    if force:
        return True
    latest = latest_valuation_trade_date(ts_code)
    if not latest:
        return True
    try:
        last = datetime.strptime(latest, "%Y%m%d")
    except ValueError:
        return True
    return datetime.now() - last > timedelta(days=_VALUATION_TTL_DAYS)


def sync_valuation_history(
    vt_symbol: str,
    *,
    days: int = 750,
    force: bool = False,
) -> ValuationProfile:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return ValuationProfile(ts_code="", vt_symbol=vt_symbol, message=f"无法解析代码: {vt_symbol}")

    ts_code = item.ts_code
    profile = build_valuation_profile(vt_symbol)
    if not _valuation_needs_sync(ts_code, force=force):
        profile.message = "估值历史仍有效，跳过同步"
        return profile

    try:
        rows = fetch_valuation_history(ts_code, days=days)
    except TushareNotConfiguredError as ex:
        profile.message = str(ex)
        return profile
    except Exception as ex:
        profile.message = str(ex)
        return profile

    count = upsert_valuation_rows(ts_code, rows)
    refreshed = build_valuation_profile(vt_symbol)
    refreshed.synced = count > 0
    refreshed.message = f"已同步 {count} 条估值历史" if count else "Tushare 未返回估值历史"
    return refreshed


def build_valuation_profile(vt_symbol: str) -> ValuationProfile:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return ValuationProfile(ts_code="", vt_symbol=vt_symbol)

    ts_code = item.ts_code
    history = list_valuation_history(ts_code, limit=750)
    pe_hist = [row.pe_ttm for row in history if row.pe_ttm is not None]
    pb_hist = [row.pb for row in history if row.pb is not None]

    try:
        fund_rows, trade_date = fetch_daily_basic_with_fallback()
    except Exception:
        fund_rows, trade_date = [], ""

    current = next((row for row in fund_rows if row.get("ts_code") == ts_code), None)
    pe = current.get("pe_ttm") if current else None
    pb = current.get("pb") if current else None
    if pe is None and history:
        pe = history[0].pe_ttm
    if pb is None and history:
        pb = history[0].pb

    return ValuationProfile(
        ts_code=ts_code,
        vt_symbol=item.vt_symbol,
        trade_date=trade_date or (history[0].trade_date if history else ""),
        pe_ttm=pe,
        pb=pb,
        total_mv=current.get("total_mv") if current else (history[0].total_mv if history else None),
        circ_mv=current.get("circ_mv") if current else (history[0].circ_mv if history else None),
        pe_percentile_3y=_percentile_rank(pe_hist, pe),
        pb_percentile_3y=_percentile_rank(pb_hist, pb),
        history_days=len(history),
    )


def sync_disclosure_calendar(vt_symbol: str) -> tuple[int, str]:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return 0, f"无法解析代码: {vt_symbol}"
    try:
        rows = fetch_disclosure_dates(item.ts_code)
    except TushareNotConfiguredError as ex:
        return 0, str(ex)
    except Exception as ex:
        return 0, str(ex)
    count = upsert_disclosure_rows(item.ts_code, rows)
    return count, f"已同步 {count} 条披露计划"


def sync_watchlist_disclosure() -> tuple[int, list[str]]:
    rows = load_watchlist_rows()
    if not rows:
        return 0, ["自选池为空"]
    total = 0
    messages: list[str] = []
    for symbol, exchange, _name in rows:
        vt_symbol = f"{symbol}.{exchange.value}"
        count, message = sync_disclosure_calendar(vt_symbol)
        total += count
        if count:
            messages.append(f"{vt_symbol}: {message}")
    summary = f"披露计划同步完成：写入 {total} 条，共 {len(rows)} 只"
    return total, [summary, *messages[:8]]


def build_sector_profile(vt_symbol: str, *, name: str = "") -> SectorProfile:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return SectorProfile(ts_code="", vt_symbol=vt_symbol, name=name)

    ts_code = item.ts_code
    industry_map = fetch_stock_industry_map()
    industry = industry_map.get(ts_code, "").strip()

    try:
        fund_rows, trade_date = fetch_daily_basic_with_fallback()
    except Exception:
        fund_rows, trade_date = [], ""

    pct_map: dict[str, float] = {}
    if trade_date:
        try:
            pct_map = fetch_daily_pct_map(trade_date)
        except Exception:
            pct_map = {}

    enriched: list[dict[str, Any]] = []
    for row in fund_rows:
        code = str(row.get("ts_code") or "")
        pct = pct_map.get(code)
        merged = dict(row)
        if pct is not None:
            merged["change_pct"] = pct
        enriched.append(merged)
    enriched = attach_industry(enriched, industry_map)

    sector_stats = compute_sector_distribution(enriched, top_n=200, min_stocks=2)
    sector_avg: float | None = None
    sector_rank: int | None = None
    for idx, stat in enumerate(sector_stats, start=1):
        if str(stat.get("industry")) == industry:
            sector_avg = stat.get("avg_change_pct")
            sector_rank = idx
            break

    peers: list[dict[str, Any]] = []
    if industry:
        same_industry = [row for row in enriched if str(row.get("industry") or "") == industry and str(row.get("ts_code") or "") != ts_code]
        same_industry.sort(
            key=lambda row: float(row.get("total_mv") or 0),
            reverse=True,
        )
        for row in same_industry[:_PEER_TOP_N]:
            mv = row.get("total_mv")
            peers.append(
                {
                    "vt_symbol": row.get("vt_symbol", ""),
                    "name": row.get("name", ""),
                    "pe_ttm": row.get("pe_ttm"),
                    "pb": row.get("pb"),
                    "total_mv_yi": round(float(mv) / 10000, 1) if mv else None,
                    "change_pct": row.get("change_pct"),
                }
            )

    disclosure_rows = list_disclosure_calendar(ts_code, limit=4)
    disclosure = [
        {
            "end_date": row.end_date,
            "pre_date": row.pre_date,
            "ann_date": row.ann_date,
        }
        for row in disclosure_rows
    ]

    sector_count = sum(1 for row in enriched if str(row.get("industry") or "") == industry)

    return SectorProfile(
        ts_code=ts_code,
        vt_symbol=item.vt_symbol,
        name=name or item.name,
        industry=industry,
        trade_date=trade_date,
        sector_count=sector_count,
        sector_avg_change_pct=sector_avg,
        sector_rank=sector_rank,
        peers=peers,
        disclosure=disclosure,
    )
