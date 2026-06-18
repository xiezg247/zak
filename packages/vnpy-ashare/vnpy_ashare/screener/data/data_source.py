"""选股数据源路由：交易时段 Redis，非交易时段 daily_basic + 交易日回退。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_rows, QuoteRowLike, QuoteRowsLike
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, screener_rows_from_mappings
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.domain.time.trade_dates import DEFAULT_LOOKBACK_DAYS, iter_trade_date_strs
from vnpy_ashare.integrations.tushare.factor_fallback import (
    fetch_daily_basic_with_fallback as _fetch_daily_basic_with_fallback,
)
from vnpy_ashare.integrations.tushare.factor_fallback import (
    fetch_moneyflow_with_fallback as _fetch_moneyflow_with_fallback,
)
from vnpy_ashare.integrations.tushare.factors import fetch_daily_pct_map
from vnpy_ashare.integrations.tushare.limit_list_fallback import fetch_limit_list_with_fallback
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.quotes.core.screening_snapshot_router import (
    load_screening_quote_snapshot,
    register_uncached_quote_snapshot_loader,
)
from vnpy_ashare.quotes.market.moneyflow_kind import enrich_moneyflow_row_with_kind, row_has_moneyflow_fields
from vnpy_ashare.screener.data.quotes_loader import (
    MarketQuotesLoadError,
    MarketQuotesSnapshot,
    load_market_quote_rows,
)

__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "MarketQuotesLoadError",
    "MarketQuotesSnapshot",
    "daily_basic_to_quote_rows",
    "enrich_recipe_rows",
    "fetch_daily_basic_with_fallback",
    "fetch_fundamental_screening_rows",
    "fetch_limit_list_with_fallback",
    "fetch_moneyflow_with_fallback",
    "iter_trade_date_strs",
    "load_screening_quote_snapshot",
    "load_screening_quote_snapshot_uncached",
    "merge_quotes_into_fundamentals",
    "resolve_result_source_tag",
]


def merge_quotes_into_fundamentals(
    fund_rows: list[dict[str, Any]],
    quote_rows: QuoteRowsLike,
) -> list[dict[str, Any]]:
    """用 Redis 实时价/换手覆盖 daily_basic 同标的字段。"""
    quote_map = quote_rows_by_vt_symbol(quote_rows)
    merged: list[dict[str, Any]] = []
    for row in fund_rows:
        item = dict(row)
        quote = quote_map.get(str(item.get("vt_symbol", "")).strip())
        if quote is None:
            merged.append(item)
            continue
        last_price = quote.get("last_price")
        if last_price:
            item["close"] = float(last_price)
        turnover = quote.get("turnover_rate")
        if turnover:
            item["turnover_rate"] = float(turnover)
        item["source"] = "quote+tushare"
        merged.append(item)
    return merged


def fetch_daily_basic_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], str]:
    return _fetch_daily_basic_with_fallback(max_lookback=max_lookback, start=start)


def fetch_moneyflow_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], str]:
    return _fetch_moneyflow_with_fallback(max_lookback=max_lookback, start=start)


def _merge_moneyflow_into_quote_rows(quote_rows: list[dict[str, Any]], mf_rows: list[dict[str, Any]]) -> None:
    mf_map = quote_rows_by_vt_symbol(mf_rows)
    for row in quote_rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        mf = mf_map.get(vt_symbol)
        if mf is None:
            continue
        for key in (
            "net_mf_amount",
            "buy_elg_amount",
            "sell_elg_amount",
            "buy_lg_amount",
            "sell_lg_amount",
            "buy_md_amount",
            "sell_md_amount",
            "moneyflow_source",
        ):
            if row.get(key) in (None, "", 0, 0.0) and mf.get(key) not in (None, "", 0, 0.0):
                row[key] = mf[key]


def daily_basic_to_quote_rows(
    rows: list[dict[str, Any]],
    *,
    trade_date: str,
    pct_map: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """将 daily_basic 行转为行情选股可用格式（保留市值字段供硬过滤）。"""
    pct_map = pct_map or {}
    quote_rows: list[dict[str, Any]] = []
    for row in rows:
        ts_code = str(row.get("ts_code", ""))
        total_mv = float(row.get("total_mv") or 0)
        circ_mv = float(row.get("circ_mv") or 0)
        close = float(row.get("close") or 0)
        quote_rows.append(
            {
                "symbol": row.get("symbol", ""),
                "name": row.get("name", ""),
                "vt_symbol": row.get("vt_symbol", ""),
                "last_price": close,
                "close": close,
                "change_pct": pct_map.get(ts_code, 0.0),
                "turnover_rate": row.get("turnover_rate", 0),
                # volume_ratio 不是成交量，勿写入 volume（否则硬过滤成交额估算失真）
                "volume_ratio": row.get("volume_ratio", 0),
                "pe_ttm": row.get("pe_ttm"),
                "pb": row.get("pb"),
                "total_mv": total_mv,
                "circ_mv": circ_mv,
                "trade_date": trade_date,
                "source": "tushare",
            }
        )
    return quote_rows


def load_screening_quote_snapshot_uncached() -> MarketQuotesSnapshot:
    """
    行情类选股数据源（无 ScreeningContext 缓存）：
    - 交易时段：Redis 实时快照
    - 非交易时段：Tushare daily_basic（回退交易日）+ daily 涨跌幅
    - 仍无数据时：尝试 Redis 陈旧快照
    """
    if is_ashare_trading_session():
        return load_market_quote_rows()

    rows, trade_date = fetch_daily_basic_with_fallback()
    if rows:
        pct_map = fetch_daily_pct_map(trade_date)
        quote_rows = daily_basic_to_quote_rows(rows, trade_date=trade_date, pct_map=pct_map)
        try:
            mf_rows, _mf_date = fetch_moneyflow_with_fallback()
            if mf_rows:
                _merge_moneyflow_into_quote_rows(quote_rows, mf_rows)
        except Exception:
            pass
        return MarketQuotesSnapshot(
            rows=coerce_quote_rows(quote_rows),
            updated_at=trade_date,
            total=len(quote_rows),
            source="tushare",
        )

    return load_market_quote_rows()


def fetch_fundamental_screening_rows() -> tuple[list[dict[str, Any]], str, str]:
    """
    基本面类选股（低 PE / 中大盘）：
    - 交易时段：daily_basic（跳过当日空数据并回退）+ Redis 实时价/换手合并
    - 非交易时段：daily_basic 回退
    返回 (rows, data_date, source_tag)。
    """
    trading = is_ashare_trading_session()
    start: date | None = None
    if trading:
        # 盘中 daily_basic 当日常未入库，直接从上一交易日开始回退
        start = last_trading_day(on_or_before=last_trading_day() - timedelta(days=1))

    rows, trade_date = fetch_daily_basic_with_fallback(start=start)
    if not rows:
        raise RuntimeError(f"Tushare daily_basic 在最近 {DEFAULT_LOOKBACK_DAYS} 个交易日均无数据，请稍后重试或检查积分权限。")

    source = "tushare"
    if trading:
        try:
            snapshot = load_market_quote_rows()
            rows = merge_quotes_into_fundamentals(rows, snapshot.rows)
            source = "quote+tushare"
        except MarketQuotesLoadError:
            pass

    return rows, trade_date, source


def resolve_result_source_tag(source: str) -> str:
    """将内部 source 标签转为 UI 展示文案。"""
    if source == "radar":
        return "雷达共振"
    if source == "radar_leader":
        return "雷达龙头"
    if source == "industry":
        return "行业成分"
    if source == "quote+tushare":
        return "Redis+Tushare"
    if source == "tushare":
        return "Tushare"
    return "Redis 行情"


def _missing_display_value(value: Any) -> bool:
    return value is None or value == ""


def enrich_recipe_rows(rows: QuoteRowsLike) -> list[ScreenerResultRow]:
    """补全配方结果展示字段（各维度 row 通常只含单维度指标）。"""
    if not rows:
        return []

    vt_symbols = {str(row.get("vt_symbol") or "") for row in rows} - {""}
    if not vt_symbols:
        return []

    fund_map: dict[str, QuoteRow] = {}
    mf_map: dict[str, QuoteRow] = {}
    pct_map: dict[str, float] = {}

    try:
        fund_rows, trade_date, _ = fetch_fundamental_screening_rows()
        fund_map = quote_rows_by_vt_symbol(fund_rows)
        pct_map = fetch_daily_pct_map(trade_date)
    except Exception:
        pass

    try:
        mf_rows, _trade_date = fetch_moneyflow_with_fallback()
        mf_map = quote_rows_by_vt_symbol(mf_rows)
    except Exception:
        pass

    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        vt_symbol = str(item.get("vt_symbol") or "").strip()
        fund = fund_map.get(vt_symbol)
        mf = mf_map.get(vt_symbol)
        fund_payload = fund.to_dict() if fund is not None else {}
        mf_payload = mf.to_dict() if mf is not None else {}
        ts_code = str(fund_payload.get("ts_code") or mf_payload.get("ts_code") or "")

        if _missing_display_value(item.get("symbol")) and fund_payload.get("symbol"):
            item["symbol"] = fund_payload["symbol"]
        if _missing_display_value(item.get("name")):
            item["name"] = fund_payload.get("name") or mf_payload.get("name") or item.get("name", "")

        if _missing_display_value(item.get("change_pct")):
            change = item.get("pct_chg")
            if _missing_display_value(change) and ts_code:
                change = pct_map.get(ts_code)
            if not _missing_display_value(change):
                item["change_pct"] = change

        for key in ("turnover_rate", "pe_ttm", "close", "volume_ratio", "total_mv", "circ_mv", "pb", "trade_date"):
            if _missing_display_value(item.get(key)) and not _missing_display_value(fund_payload.get(key)):
                item[key] = fund_payload[key]

        for key in ("net_mf_amount", "buy_elg_amount", "sell_elg_amount"):
            if _missing_display_value(item.get(key)) and not _missing_display_value(mf_payload.get(key)):
                item[key] = mf_payload[key]

        for key in ("buy_lg_amount", "sell_lg_amount", "buy_md_amount", "sell_md_amount"):
            if _missing_display_value(item.get(key)) and not _missing_display_value(mf_payload.get(key)):
                item[key] = mf_payload[key]

        if _missing_display_value(item.get("last_price")) and not _missing_display_value(item.get("close")):
            item["last_price"] = item["close"]

        if _missing_display_value(item.get("flow_kind")):
            if row_has_moneyflow_fields(item):
                item = enrich_moneyflow_row_with_kind(item)

        enriched.append(item)
    return screener_rows_from_mappings(enriched)


register_uncached_quote_snapshot_loader(load_screening_quote_snapshot_uncached)
