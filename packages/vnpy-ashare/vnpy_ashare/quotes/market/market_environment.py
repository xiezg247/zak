"""大盘环境指标（恐贪指数、北向资金）。"""

from __future__ import annotations

import logging

from vnpy_ashare.domain.market.environment import MarketEnvironmentSnapshot
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.integrations.tushare.factor_fallback import resolve_latest_factor_trade_date
from vnpy_ashare.integrations.tushare.factors import fetch_moneyflow_hsgt_window
from vnpy_ashare.screener.sentiment.fear_greed_provider import try_fetch_fear_greed_index

logger = logging.getLogger(__name__)

__all__ = ["MarketEnvironmentSnapshot", "format_north_money_hsgt", "load_market_environment"]


def format_north_money_hsgt(north_money: float | None) -> str:
    """Tushare moneyflow_hsgt.north_money 单位为百万元。"""
    if north_money is None:
        return "—"
    yi = north_money / 100.0
    if abs(yi) >= 0.01:
        return f"{yi:+.2f}亿"
    return f"{north_money:+.0f}百万"


def load_market_environment(
    *,
    force: bool = False,
    factor_trade_date: str | None = None,
) -> MarketEnvironmentSnapshot:
    """加载恐贪指数与北向资金（优先本地 Tushare 缓存）。"""
    factor_trade_date = factor_trade_date or resolve_latest_factor_trade_date()
    calendar_trade_date = last_trading_day().strftime("%Y%m%d")
    fear_index: float | None = None
    fear_label = ""
    fear_trade_date = ""
    try:
        snapshot = try_fetch_fear_greed_index(trade_date=factor_trade_date)
        if snapshot is not None:
            fear_index = float(snapshot.index)
            fear_label = str(snapshot.label or "")
            raw_date = str(snapshot.trade_date or factor_trade_date)
            fear_trade_date = raw_date.replace("-", "")[:8]
    except Exception:
        logger.debug("恐贪指数加载失败", exc_info=True)

    north_money: float | None = None
    north_trade_date = ""
    try:
        rows, _anchor = fetch_moneyflow_hsgt_window(trade_date=calendar_trade_date, force=force)
        if rows:
            latest = max(rows, key=lambda row: str(row.get("trade_date") or ""))
            raw = latest.get("north_money")
            if raw is not None:
                north_money = float(raw)
            north_trade_date = str(latest.get("trade_date") or calendar_trade_date or "")
    except Exception:
        logger.debug("北向资金加载失败", exc_info=True)

    return MarketEnvironmentSnapshot(
        fear_greed_index=fear_index,
        fear_greed_label=fear_label,
        fear_greed_trade_date=fear_trade_date,
        north_money=north_money,
        north_trade_date=north_trade_date,
    )
