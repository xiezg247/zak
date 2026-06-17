"""A 股全市场恐贪指数（SentimentService）。

六分项加权：涨跌广度、涨跌停、指数动量、成交活跃、波动率、北向资金；缓存 TTL 10 分钟。
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime, timedelta
from typing import Any

from vnpy_ashare.domain.sentiment.fear_greed import FearGreedComponent, FearGreedSnapshot
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.integrations.tushare import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.services.base import BaseService

FEAR_GREED_LABELS: tuple[tuple[float, str], ...] = (
    (25, "极度恐惧"),
    (45, "恐惧"),
    (55, "中性"),
    (75, "贪婪"),
    (101, "极度贪婪"),
)

COMPONENT_WEIGHTS: dict[str, float] = {
    "breadth": 0.25,
    "limit_sentiment": 0.20,
    "index_momentum": 0.20,
    "volume_heat": 0.15,
    "volatility": 0.10,
    "northbound": 0.10,
}

_CACHE_TTL_SEC = 600


def label_for_index(index: float) -> str:
    """指数值 → 极度恐惧 / 恐惧 / 中性 / 贪婪 / 极度贪婪。"""
    for bound, label in FEAR_GREED_LABELS:
        if index < bound:
            return label
    return "极度贪婪"


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _linear_map(value: float, *, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    if value <= low:
        return 0.0
    if value >= high:
        return 100.0
    return (value - low) / (high - low) * 100.0


class SentimentService(BaseService):
    """基于 Tushare 的 A 股恐贪指数。"""

    def __init__(self, engine) -> None:
        super().__init__(engine)
        self._cache: dict[str, tuple[float, FearGreedSnapshot]] = {}

    def compute_fear_greed(
        self,
        *,
        trade_date: str | None = None,
        include_components: bool = True,
    ) -> FearGreedSnapshot:
        """计算指定交易日恐贪指数；默认最近交易日，结果缓存 10 分钟。"""
        day = self._resolve_trade_date(trade_date)
        cache_key = day.strftime("%Y%m%d")
        cached = self._cache.get(cache_key)
        now = time.monotonic()
        if cached is not None and now - cached[0] < _CACHE_TTL_SEC:
            snapshot = cached[1]
            if include_components:
                return snapshot
            return FearGreedSnapshot(
                index=snapshot.index,
                label=snapshot.label,
                trade_date=snapshot.trade_date,
                as_of=snapshot.as_of,
                components=snapshot.components,
                warnings=snapshot.warnings,
                sources=snapshot.sources,
                disclaimer=snapshot.disclaimer,
            )

        snapshot = self._compute_for_day(day)
        self._cache[cache_key] = (now, snapshot)
        if not include_components:
            return FearGreedSnapshot(
                index=snapshot.index,
                label=snapshot.label,
                trade_date=snapshot.trade_date,
                as_of=snapshot.as_of,
                components=snapshot.components,
                warnings=snapshot.warnings,
                sources=snapshot.sources,
                disclaimer=snapshot.disclaimer,
            )
        return snapshot

    def _resolve_trade_date(self, trade_date: str | None) -> date:
        if trade_date:
            text = trade_date.strip()
            if len(text) == 8 and text.isdigit():
                return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        return last_trading_day()

    def _compute_for_day(self, day: date) -> FearGreedSnapshot:

        trade_date = day.strftime("%Y%m%d")
        warnings: list[str] = []
        sources = ["tushare"]
        components: list[FearGreedComponent] = []

        try:
            pro = get_tushare_pro()
        except TushareNotConfiguredError as ex:
            raise RuntimeError(str(ex)) from ex

        breadth = self._component_breadth(pro, trade_date, warnings)
        if breadth is not None:
            components.append(breadth)

        limit_sentiment = self._component_limit_sentiment(pro, trade_date, warnings)
        if limit_sentiment is not None:
            components.append(limit_sentiment)

        index_momentum = self._component_index_momentum(pro, trade_date, warnings)
        if index_momentum is not None:
            components.append(index_momentum)

        volume_heat = self._component_volume_heat(pro, trade_date, warnings)
        if volume_heat is not None:
            components.append(volume_heat)

        volatility = self._component_volatility(pro, trade_date, warnings)
        if volatility is not None:
            components.append(volatility)

        northbound = self._component_northbound(pro, trade_date, warnings)
        if northbound is not None:
            components.append(northbound)

        if not components:
            raise RuntimeError("恐贪指数分项均不可用，请稍后重试")

        index = self._weighted_index(components)
        return FearGreedSnapshot(
            index=round(index, 1),
            label=label_for_index(index),
            trade_date=f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}",
            as_of=format_china_datetime(),
            components=components,
            warnings=warnings,
            sources=sources,
        )

    @staticmethod
    def _weighted_index(components: list[FearGreedComponent]) -> float:
        total_weight = sum(item.weight for item in components)
        if total_weight <= 0:
            return 50.0
        score = sum(item.score * item.weight for item in components) / total_weight
        return _clamp_score(score)

    @staticmethod
    def _component_breadth(pro, trade_date: str, warnings: list[str]) -> FearGreedComponent | None:
        try:
            frame = pro.daily(trade_date=trade_date, fields="ts_code,pct_chg")
        except Exception as ex:
            warnings.append(f"涨跌广度不可用：{ex}")
            return None
        if frame is None or frame.empty:
            warnings.append("涨跌广度：当日 daily 无数据")
            return None

        up = down = flat = 0
        for pct in frame["pct_chg"].tolist():
            if pct is None or (isinstance(pct, float) and math.isnan(pct)):
                continue
            value = float(pct)
            if value > 0:
                up += 1
            elif value < 0:
                down += 1
            else:
                flat += 1
        tradable = up + down + flat
        if tradable <= 0:
            warnings.append("涨跌广度：无有效样本")
            return None
        ratio = up / tradable
        score = _clamp_score(ratio * 100)
        return FearGreedComponent(
            name="breadth",
            score=score,
            weight=COMPONENT_WEIGHTS["breadth"],
            raw={"up": up, "down": down, "flat": flat, "up_ratio": round(ratio, 4)},
            hint="上涨家数占比越高越偏贪婪",
        )

    @staticmethod
    def _component_limit_sentiment(pro, trade_date: str, warnings: list[str]) -> FearGreedComponent | None:
        try:
            frame = pro.limit_list_d(trade_date=trade_date, fields="ts_code,limit")
        except Exception as ex:
            warnings.append(f"涨跌停情绪不可用：{ex}")
            return None
        if frame is None or frame.empty:
            limit_up = limit_down = 0
        else:
            limit_up = int((frame["limit"] == "U").sum())
            limit_down = int((frame["limit"] == "D").sum())
        total = limit_up + limit_down
        if total <= 0:
            score = 50.0
            ratio = 0.5
        else:
            ratio = limit_up / total
            score = _clamp_score(ratio * 100)
        return FearGreedComponent(
            name="limit_sentiment",
            score=score,
            weight=COMPONENT_WEIGHTS["limit_sentiment"],
            raw={"limit_up": limit_up, "limit_down": limit_down, "up_ratio": round(ratio, 4)},
            hint="涨停家数相对跌停越多越偏贪婪",
        )

    @staticmethod
    def _component_index_momentum(pro, trade_date: str, warnings: list[str]) -> FearGreedComponent | None:
        try:
            frame = pro.index_daily(
                ts_code="000300.SH",
                end_date=trade_date,
                fields="trade_date,close,pct_chg",
            )
        except Exception as ex:
            warnings.append(f"指数动量不可用：{ex}")
            return None
        if frame is None or frame.empty:
            warnings.append("指数动量：沪深300 无数据")
            return None
        frame = frame.sort_values("trade_date")
        closes = [float(v) for v in frame["close"].tolist() if v is not None]
        if len(closes) < 6:
            warnings.append("指数动量：历史样本不足")
            return None
        ret5 = (closes[-1] / closes[-6] - 1.0) * 100
        score = _clamp_score(_linear_map(ret5, low=-6.0, high=6.0))
        return FearGreedComponent(
            name="index_momentum",
            score=score,
            weight=COMPONENT_WEIGHTS["index_momentum"],
            raw={"index": "000300.SH", "return_5d_pct": round(ret5, 2)},
            hint="沪深300 近 5 日越强越偏贪婪",
        )

    @staticmethod
    def _component_volume_heat(pro, trade_date: str, warnings: list[str]) -> FearGreedComponent | None:
        try:
            frame = pro.index_daily(
                ts_code="000001.SH",
                end_date=trade_date,
                fields="trade_date,amount",
            )
        except Exception as ex:
            warnings.append(f"成交活跃度不可用：{ex}")
            return None
        if frame is None or frame.empty:
            warnings.append("成交活跃度：上证综指成交额无数据")
            return None
        frame = frame.sort_values("trade_date")
        amounts = [float(v) for v in frame["amount"].tolist() if v not in (None, 0)]
        if len(amounts) < 6:
            warnings.append("成交活跃度：样本不足")
            return None
        today = amounts[-1]
        base = sum(amounts[-21:-1]) / max(len(amounts[-21:-1]), 1)
        ratio = today / base if base else 1.0
        score = _clamp_score(_linear_map(ratio, low=0.6, high=1.6))
        return FearGreedComponent(
            name="volume_heat",
            score=score,
            weight=COMPONENT_WEIGHTS["volume_heat"],
            raw={"index": "000001.SH", "amount_ratio_20d": round(ratio, 3)},
            hint="成交额相对 20 日均值越高越偏贪婪",
        )

    @staticmethod
    def _component_volatility(pro, trade_date: str, warnings: list[str]) -> FearGreedComponent | None:
        try:
            frame = pro.index_daily(
                ts_code="000300.SH",
                end_date=trade_date,
                fields="trade_date,close",
            )
        except Exception as ex:
            warnings.append(f"波动率不可用：{ex}")
            return None
        if frame is None or frame.empty:
            warnings.append("波动率：沪深300 无数据")
            return None
        frame = frame.sort_values("trade_date")
        closes = [float(v) for v in frame["close"].tolist() if v is not None]
        if len(closes) < 22:
            warnings.append("波动率：样本不足")
            return None
        returns = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))]
        recent = returns[-20:]
        long = returns[-60:] if len(returns) >= 60 else returns
        vol20 = _std(recent)
        vol60 = _std(long)
        if vol60 <= 0:
            score = 50.0
            ratio = 1.0
        else:
            ratio = vol20 / vol60
            score = _clamp_score(_linear_map(1.4 - ratio, low=0.0, high=1.0))
        return FearGreedComponent(
            name="volatility",
            score=score,
            weight=COMPONENT_WEIGHTS["volatility"],
            raw={"vol20": round(vol20, 5), "vol60": round(vol60, 5), "ratio": round(ratio, 3)},
            hint="波动率相对偏低时更偏贪婪",
        )

    @staticmethod
    def _component_northbound(pro, trade_date: str, warnings: list[str]) -> FearGreedComponent | None:
        try:
            frame = pro.moneyflow_hsgt(trade_date=trade_date, fields="trade_date,north_money")
        except Exception as ex:
            warnings.append(f"北向资金不可用：{ex}")
            return None
        if frame is None or frame.empty:
            warnings.append("北向资金：当日无数据")
            return None
        try:
            end_frame = pro.moneyflow_hsgt(
                start_date=_shift_trade_date(trade_date, -25),
                end_date=trade_date,
                fields="trade_date,north_money",
            )
        except Exception:
            end_frame = frame
        today_val = float(frame.iloc[-1]["north_money"] or 0)
        history = [float(v) for v in end_frame["north_money"].tolist() if v is not None] if end_frame is not None and not end_frame.empty else [today_val]
        low = min(history) if history else today_val
        high = max(history) if history else today_val
        score = _clamp_score(_linear_map(today_val, low=low, high=high))
        return FearGreedComponent(
            name="northbound",
            score=score,
            weight=COMPONENT_WEIGHTS["northbound"],
            raw={"north_money": round(today_val, 2), "range_low": round(low, 2), "range_high": round(high, 2)},
            hint="北向净流入越高越偏贪婪",
        )


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def _shift_trade_date(trade_date: str, offset: int) -> str:
    day = datetime.strptime(trade_date, "%Y%m%d").date()
    return (day + timedelta(days=offset)).strftime("%Y%m%d")


from vnpy_ashare.screener.sentiment import fear_greed_index as _fear_greed_bootstrap  # noqa: E402, F401
