"""K 线数据查询 Service。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.bar_access import (
    PeriodBarOverview,
    build_symbol_name_map,
    get_period_overview,
    iter_bar_overviews,
    load_scope_bars,
    universe_exists,
)
from vnpy_ashare.services.base import BaseService

LOOKBACK_MAX = 250


class BarService(BaseService):
    """K 线概览、历史数据加载、区间统计。"""

    def get_overview(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str = "daily",
    ) -> PeriodBarOverview | None:
        return get_period_overview(symbol, exchange, scope)

    def load_bars(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str = "daily",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[BarData]:
        s = start or datetime(1990, 1, 1)
        e = end or datetime.now()
        return load_scope_bars(symbol, exchange, scope, s, e)

    def get_return(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str = "daily",
        lookback_days: int = 20,
    ) -> dict[str, Any]:
        days = max(2, min(lookback_days, LOOKBACK_MAX))
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days * 2)
        bars = load_scope_bars(symbol, exchange, scope, start_dt, end_dt)
        if len(bars) < 2:
            return {
                "symbol": f"{symbol}.{exchange.value}",
                "scope": scope,
                "message": "暂无足够 K 线数据",
            }
        tail = bars[-days:] if len(bars) >= days else bars
        first_close = tail[0].close_price
        last_close = tail[-1].close_price
        return {
            "symbol": f"{symbol}.{exchange.value}",
            "scope": scope,
            "lookback_days": len(tail),
            "start": tail[0].datetime.strftime("%Y-%m-%d"),
            "end": tail[-1].datetime.strftime("%Y-%m-%d"),
            "return_pct": round((last_close - first_close) / first_close * 100, 2),
            "close_start": round(first_close, 2),
            "close_end": round(last_close, 2),
        }

    def list_downloaded(self, scope: str = "daily") -> list[PeriodBarOverview]:
        return iter_bar_overviews(scope=scope)

    def iter_overviews(self, scope: str) -> list[PeriodBarOverview]:
        """遍历指定 scope 的 K 线概览。"""
        return iter_bar_overviews(scope=scope)

    def build_symbol_name_map(self) -> dict[tuple[str, Exchange], str]:
        return build_symbol_name_map()

    def universe_exists(self) -> bool:
        return universe_exists()

    def publish_data_manager_context(self) -> None:
        publish_data_manager_page_context()


def publish_data_manager_page_context() -> None:
    """推送数据管理页 AI 上下文。"""
    from vnpy_ashare.ai.context import AiContextData
    from vnpy_ashare.ai.context_store import set_ai_context
    from vnpy_llm.ui.floating_actions import enrich_context_with_actions

    daily_symbols: set[tuple[str, str]] = set()
    minute_symbols: set[tuple[str, str]] = set()
    daily_bars = 0
    minute_bars = 0

    for overview in iter_bar_overviews(scope="daily"):
        daily_symbols.add((overview.symbol, overview.exchange.value))
        daily_bars += overview.count

    for overview in iter_bar_overviews(scope="1m"):
        minute_symbols.add((overview.symbol, overview.exchange.value))
        minute_bars += overview.count

    extra_lines = [
        "你正在协助用户查看本地 K 线数据覆盖；请基于工具与上下文回答，禁止编造。",
        f"日线：{len(daily_symbols)} 组标的，共 {daily_bars} 根 K 线",
        f"分钟线：{len(minute_symbols)} 组标的，共 {minute_bars} 根 K 线",
        "补全数据请引导用户使用「自选 / 本地」页或「工具 → 立即执行」。",
    ]
    set_ai_context(enrich_context_with_actions(AiContextData(page="数据管理", extra="\n".join(extra_lines))))
