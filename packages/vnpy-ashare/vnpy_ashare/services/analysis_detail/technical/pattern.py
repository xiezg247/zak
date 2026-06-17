"""历史走势统计摘要（描述性，非预测）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.services.analysis_detail.technical.base import _TechnicalAnalyzerBase


class TechnicalPatternMixin(_TechnicalAnalyzerBase):
    def historical_pattern_summary(
        self,
        symbol: str,
        *,
        lookback: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        """历史走势统计摘要（描述性，非预测）。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        lookback = max(5, min(int(lookback or 20), 120))
        bars = self._engine.bar_service.load_bars(
            item.symbol,
            item.exchange,
            scope or "daily",
        )
        if len(bars) < lookback:
            return {
                "symbol": item.vt_symbol,
                "name": item.name,
                "lookback_requested": lookback,
                "local_available": False,
                "warnings": ["本地 K 线不足，将尝试问小达 MCP 兜底"],
                "sources": ["bar"],
            }

        tail = bars[-lookback:]
        closes = [bar.close_price for bar in tail]
        highs = [bar.high_price for bar in tail]
        lows = [bar.low_price for bar in tail]
        first_close = closes[0]
        last_close = closes[-1]
        return_pct = round((last_close - first_close) / first_close * 100, 2) if first_close else 0.0

        daily_changes: list[float] = []
        for index in range(1, len(closes)):
            prev = closes[index - 1]
            if prev:
                daily_changes.append((closes[index] - prev) / prev * 100)

        volatility_pct = 0.0
        if len(daily_changes) >= 2:
            mean_change = sum(daily_changes) / len(daily_changes)
            variance = sum((value - mean_change) ** 2 for value in daily_changes) / len(daily_changes)
            volatility_pct = round(variance**0.5, 2)

        range_pct = 0.0
        if first_close:
            range_pct = round((max(highs) - min(lows)) / first_close * 100, 2)

        up_streak = down_streak = 0
        max_up = max_down = 0
        for change in daily_changes:
            if change > 0:
                up_streak += 1
                down_streak = 0
            elif change < 0:
                down_streak += 1
                up_streak = 0
            else:
                up_streak = down_streak = 0
            max_up = max(max_up, up_streak)
            max_down = max(max_down, down_streak)

        if up_streak > 0:
            current_streak_direction = "up"
            current_streak_days = up_streak
        elif down_streak > 0:
            current_streak_direction = "down"
            current_streak_days = down_streak
        else:
            current_streak_direction = "flat"
            current_streak_days = 0

        trend_label = self._describe_trend(return_pct, volatility_pct)
        pattern_label = self._describe_pattern(
            return_pct=return_pct,
            volatility_pct=volatility_pct,
            range_pct=range_pct,
            max_up=max_up,
            max_down=max_down,
        )

        technical = self.technical_snapshot(symbol, lookback=min(lookback, 60), scope=scope)

        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "scope": scope or "daily",
            "lookback_days": len(tail),
            "start": tail[0].datetime.strftime("%Y-%m-%d"),
            "end": tail[-1].datetime.strftime("%Y-%m-%d"),
            "as_of": tail[-1].datetime.strftime("%Y-%m-%d"),
            "return_pct": return_pct,
            "close_start": round(first_close, 2),
            "close_end": round(last_close, 2),
            "high": round(max(highs), 2),
            "low": round(min(lows), 2),
            "range_pct": range_pct,
            "volatility_pct": volatility_pct,
            "max_consecutive_up_days": max_up,
            "max_consecutive_down_days": max_down,
            "current_streak_days": current_streak_days,
            "current_streak_direction": current_streak_direction,
            "trend_label": trend_label,
            "pattern_label": pattern_label,
            "ma_alignment": technical.get("ma_alignment"),
            "volume_ratio_5d": technical.get("volume_ratio_5d"),
            "warnings": list(technical.get("warnings") or []),
            "local_available": True,
            "data_quality": "local",
            "sources": ["bar"],
            "disclaimer": "以上均为历史区间统计，不代表对未来走势的判断或预测。",
        }

    @staticmethod
    def _describe_trend(return_pct: float, volatility_pct: float) -> str:
        if return_pct >= 5:
            base = "区间明显上行"
        elif return_pct <= -5:
            base = "区间明显下行"
        elif return_pct >= 1:
            base = "区间温和上行"
        elif return_pct <= -1:
            base = "区间温和下行"
        else:
            base = "区间横盘震荡"
        if volatility_pct >= 3:
            return f"{base}，波动偏大"
        if volatility_pct <= 1:
            return f"{base}，波动偏低"
        return base

    @staticmethod
    def _describe_pattern(
        *,
        return_pct: float,
        volatility_pct: float,
        range_pct: float,
        max_up: int,
        max_down: int,
    ) -> str:
        parts: list[str] = []
        if abs(return_pct) < 2 and range_pct < 8:
            parts.append("窄幅震荡")
        elif return_pct > 0 and max_up >= 3:
            parts.append("阶段性连阳")
        elif return_pct < 0 and max_down >= 3:
            parts.append("阶段性连阴")
        elif volatility_pct >= 3.5:
            parts.append("高波动")
        else:
            parts.append("常规波动")
        if return_pct > 2:
            parts.append("重心上移")
        elif return_pct < -2:
            parts.append("重心下移")
        return " · ".join(parts)
