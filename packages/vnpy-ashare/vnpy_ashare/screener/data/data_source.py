"""选股数据源路由：交易时段 Redis，非交易时段 daily_basic + 交易日回退。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

from vnpy_ashare.domain.calendar import last_trading_day
from vnpy_ashare.domain.market_hours import is_ashare_trading_session
from vnpy_ashare.integrations.tushare.factors import (
    fetch_daily_basic,
    fetch_daily_pct_map,
    fetch_moneyflow,
)
from vnpy_ashare.screener.data.quotes_loader import (
    MarketQuotesLoadError,
    MarketQuotesSnapshot,
    load_market_quote_rows,
)

DEFAULT_LOOKBACK_DAYS = 10


def merge_quotes_into_fundamentals(
    fund_rows: list[dict[str, Any]],
    quote_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """用 Redis 实时价/换手覆盖 daily_basic 同标的字段。"""
    quote_map = {str(row.get("vt_symbol", "")): row for row in quote_rows if row.get("vt_symbol")}
    merged: list[dict[str, Any]] = []
    for row in fund_rows:
        item = dict(row)
        quote = quote_map.get(str(item.get("vt_symbol", "")))
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


def iter_trade_date_strs(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> Iterator[str]:
    """从 start（默认最近交易日）向前遍历交易日。"""
    current = start or last_trading_day()
    for _ in range(max(1, max_lookback)):
        yield current.strftime("%Y%m%d")
        current = last_trading_day(on_or_before=current - timedelta(days=1))


def fetch_daily_basic_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """按交易日回退拉取 daily_basic，直到有数据或耗尽 lookback。"""
    last_tried = ""
    for trade_date in iter_trade_date_strs(max_lookback=max_lookback, start=start):
        last_tried = trade_date
        rows, _ = fetch_daily_basic(trade_date=trade_date)
        if rows:
            return rows, trade_date
    return [], last_tried


def fetch_moneyflow_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """按交易日回退拉取 moneyflow，直到有数据或耗尽 lookback。"""
    last_tried = ""
    for trade_date in iter_trade_date_strs(max_lookback=max_lookback, start=start):
        last_tried = trade_date
        rows, _ = fetch_moneyflow(trade_date=trade_date)
        if rows:
            return rows, trade_date
    return [], last_tried


def fetch_limit_list_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
    limit_type: str | None = "U",
) -> tuple[list[dict[str, Any]], str]:
    """按交易日回退拉取涨跌停列表（默认涨停）。"""
    from vnpy_ashare.integrations.tushare.factors import fetch_limit_list_d

    last_tried = ""
    for trade_date in iter_trade_date_strs(max_lookback=max_lookback, start=start):
        last_tried = trade_date
        rows, _ = fetch_limit_list_d(trade_date=trade_date, limit_type=limit_type)
        if rows:
            return rows, trade_date
    return [], last_tried


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
        return MarketQuotesSnapshot(
            rows=quote_rows,
            updated_at=trade_date,
            total=len(quote_rows),
            source="tushare",
        )

    return load_market_quote_rows()


def load_screening_quote_snapshot() -> MarketQuotesSnapshot:
    """行情快照；活跃 ScreeningContext 内复用同一份数据。"""
    from vnpy_ashare.screener.data.screening_context import get_cached_quote_snapshot

    cached = get_cached_quote_snapshot()
    if cached is not None:
        return cached
    return load_screening_quote_snapshot_uncached()


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
    if source == "industry":
        return "行业成分"
    if source == "quote+tushare":
        return "Redis+Tushare"
    if source == "tushare":
        return "Tushare"
    return "Redis 行情"


def _missing_display_value(value: Any) -> bool:
    return value is None or value == ""


def enrich_recipe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """补全配方结果展示字段（各维度 row 通常只含单维度指标）。"""
    if not rows:
        return rows

    vt_symbols = {str(row.get("vt_symbol") or "") for row in rows} - {""}
    if not vt_symbols:
        return rows

    fund_map: dict[str, dict[str, Any]] = {}
    mf_map: dict[str, dict[str, Any]] = {}
    pct_map: dict[str, float] = {}

    try:
        fund_rows, trade_date, _ = fetch_fundamental_screening_rows()
        fund_map = {str(row.get("vt_symbol") or ""): row for row in fund_rows if row.get("vt_symbol")}
        pct_map = fetch_daily_pct_map(trade_date)
    except Exception:
        pass

    try:
        mf_rows, _trade_date = fetch_moneyflow_with_fallback()
        mf_map = {str(row.get("vt_symbol") or ""): row for row in mf_rows if row.get("vt_symbol")}
    except Exception:
        pass

    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        vt_symbol = str(item.get("vt_symbol") or "")
        fund = fund_map.get(vt_symbol, {})
        mf = mf_map.get(vt_symbol, {})
        ts_code = str(fund.get("ts_code") or mf.get("ts_code") or "")

        if _missing_display_value(item.get("symbol")) and fund.get("symbol"):
            item["symbol"] = fund["symbol"]
        if _missing_display_value(item.get("name")):
            item["name"] = fund.get("name") or mf.get("name") or item.get("name", "")

        if _missing_display_value(item.get("change_pct")):
            change = item.get("pct_chg")
            if _missing_display_value(change) and ts_code:
                change = pct_map.get(ts_code)
            if not _missing_display_value(change):
                item["change_pct"] = change

        for key in ("turnover_rate", "pe_ttm", "close", "volume_ratio", "total_mv", "circ_mv", "pb", "trade_date"):
            if _missing_display_value(item.get(key)) and not _missing_display_value(fund.get(key)):
                item[key] = fund[key]

        for key in ("net_mf_amount", "buy_elg_amount", "sell_elg_amount"):
            if _missing_display_value(item.get(key)) and not _missing_display_value(mf.get(key)):
                item[key] = mf[key]

        if _missing_display_value(item.get("last_price")) and not _missing_display_value(item.get("close")):
            item["last_price"] = item["close"]

        enriched.append(item)
    return enriched
