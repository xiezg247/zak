"""选股数据源路由：交易时段 Redis，非交易时段 daily_basic + 交易日回退。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

from vnpy_ashare.domain.calendar import last_trading_day
from vnpy_ashare.domain.market_hours import is_ashare_trading_session
from vnpy_ashare.screener.factors import (
    fetch_daily_basic,
    fetch_daily_pct_map,
    fetch_moneyflow,
    merge_quotes_into_fundamentals,
)
from vnpy_ashare.screener.quotes_loader import (
    MarketQuotesLoadError,
    MarketQuotesSnapshot,
    load_market_quote_rows,
)

DEFAULT_LOOKBACK_DAYS = 10


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


def daily_basic_to_quote_rows(
    rows: list[dict[str, Any]],
    *,
    trade_date: str,
    pct_map: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """将 daily_basic 行转为行情选股可用格式。"""
    pct_map = pct_map or {}
    quote_rows: list[dict[str, Any]] = []
    for row in rows:
        ts_code = str(row.get("ts_code", ""))
        quote_rows.append(
            {
                "symbol": row.get("symbol", ""),
                "name": row.get("name", ""),
                "vt_symbol": row.get("vt_symbol", ""),
                "last_price": row.get("close", 0),
                "change_pct": pct_map.get(ts_code, 0.0),
                "turnover_rate": row.get("turnover_rate", 0),
                "volume": row.get("volume_ratio", 0),
                "trade_date": trade_date,
            }
        )
    return quote_rows


def load_screening_quote_snapshot() -> MarketQuotesSnapshot:
    """
    行情类选股数据源：
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
    if source == "quote+tushare":
        return "Redis+Tushare"
    if source == "tushare":
        return "Tushare"
    return "Redis 行情"
