"""K 线技术面快照（均线、量比、区间收益）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.domain.time.china import format_china_date
from vnpy_ashare.services.analysis_detail.technical.base import _TechnicalAnalyzerBase


class TechnicalSnapshotMixin(_TechnicalAnalyzerBase):
    def technical_snapshot(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        scope: str = "daily",
    ) -> dict[str, Any]:
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        lookback = max(5, min(int(lookback or 60), 250))
        bars = self._engine.bar_service.load_bars(
            item.symbol,
            item.exchange,
            scope or "daily",
        )
        warnings: list[str] = []
        if len(bars) < 2:
            return {
                "symbol": item.vt_symbol,
                "scope": scope or "daily",
                "warnings": ["本地暂无足够 K 线，请先在数据管理页下载日 K"],
                "sources": ["bar"],
                "as_of": format_china_date(),
            }

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        volumes = [bar.volume for bar in tail]
        last_close = closes[-1]

        def _ma(window: int) -> float | None:
            if len(closes) < window:
                return None
            segment = closes[-window:]
            return round(sum(segment) / len(segment), 2)

        ma5, ma10, ma20, ma60 = _ma(5), _ma(10), _ma(20), _ma(60)
        ma_alignment = self._describe_ma_alignment(last_close, ma5, ma10, ma20, ma60)

        recent_vol = volumes[-5:] if len(volumes) >= 5 else volumes
        base_vol = volumes[:-5] if len(volumes) > 10 else volumes
        avg_recent = sum(recent_vol) / len(recent_vol) if recent_vol else 0
        avg_base = sum(base_vol) / len(base_vol) if base_vol else avg_recent
        volume_ratio = round(avg_recent / avg_base, 2) if avg_base else None

        period_return = self._engine.bar_service.get_return(
            item.symbol,
            item.exchange,
            scope or "daily",
            lookback_days=min(lookback, 60),
        )

        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "scope": scope or "daily",
            "as_of": tail[-1].datetime.strftime("%Y-%m-%d"),
            "bars_used": len(tail),
            "last_close": round(last_close, 2),
            "ma": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60},
            "ma_alignment": ma_alignment,
            "volume_ratio_5d": volume_ratio,
            "period_return": period_return,
            "sources": ["bar"],
            "warnings": warnings,
        }

    @staticmethod
    def _describe_ma_alignment(
        last_close: float,
        ma5: float | None,
        ma10: float | None,
        ma20: float | None,
        ma60: float | None,
    ) -> str:
        if ma5 is None or ma10 is None or ma20 is None:
            return "数据不足，无法判断均线排列"
        if ma5 > ma10 > ma20:
            trend = "短期多头排列"
        elif ma5 < ma10 < ma20:
            trend = "短期空头排列"
        else:
            trend = "均线交织"
        above = "站上" if last_close >= ma20 else "跌破"
        detail = f"{trend}，现价{above} MA20"
        if ma60 is not None:
            detail += f"，{'站上' if last_close >= ma60 else '跌破'} MA60"
        return detail
