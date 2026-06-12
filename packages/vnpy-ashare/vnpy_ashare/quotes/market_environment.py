"""大盘环境指标（恐贪指数、北向资金）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketEnvironmentSnapshot:
    fear_greed_index: float | None
    fear_greed_label: str
    north_money: float | None
    north_trade_date: str = ""


def format_north_money_hsgt(north_money: float | None) -> str:
    """Tushare moneyflow_hsgt.north_money 单位为百万元。"""
    if north_money is None:
        return "—"
    yi = north_money / 100.0
    if abs(yi) >= 0.01:
        return f"{yi:+.2f}亿"
    return f"{north_money:+.0f}百万"


def load_market_environment() -> MarketEnvironmentSnapshot:
    """加载恐贪指数与北向资金（优先本地 Tushare 缓存）。"""
    fear_index: float | None = None
    fear_label = ""
    try:
        from vnpy_ashare.screener.sentiment.sentiment_gate import try_fetch_fear_greed_index

        snapshot = try_fetch_fear_greed_index()
        if snapshot is not None:
            fear_index = float(snapshot.index)
            fear_label = str(snapshot.label or "")
    except Exception:
        pass

    north_money: float | None = None
    north_trade_date = ""
    try:
        from vnpy_ashare.integrations.tushare.factors import fetch_moneyflow_hsgt_window

        rows, trade_date = fetch_moneyflow_hsgt_window()
        if rows:
            latest = max(rows, key=lambda row: str(row.get("trade_date") or ""))
            raw = latest.get("north_money")
            if raw is not None:
                north_money = float(raw)
            north_trade_date = str(latest.get("trade_date") or trade_date or "")
    except Exception:
        pass

    return MarketEnvironmentSnapshot(
        fear_greed_index=fear_index,
        fear_greed_label=fear_label,
        north_money=north_money,
        north_trade_date=north_trade_date,
    )
