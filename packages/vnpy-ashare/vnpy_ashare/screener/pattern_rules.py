"""K 线形态识别（基于本地日 K）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy.trader.object import BarData


@dataclass(frozen=True)
class BarSeries:
    closes: list[float]
    highs: list[float]
    lows: list[float]
    volumes: list[float]

    @classmethod
    def from_bars(cls, bars: list[BarData]) -> BarSeries:
        return cls(
            closes=[bar.close_price for bar in bars],
            highs=[bar.high_price for bar in bars],
            lows=[bar.low_price for bar in bars],
            volumes=[float(bar.volume) for bar in bars],
        )


@dataclass(frozen=True)
class PatternMatch:
    score: float
    hint: str


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    segment = values[-window:]
    return sum(segment) / len(segment)


def _volume_ratio(volumes: list[float], recent: int = 5, base: int = 20) -> float | None:
    if len(volumes) < recent + base:
        return None
    avg_recent = sum(volumes[-recent:]) / recent
    avg_base = sum(volumes[-(recent + base) : -recent]) / base
    if avg_base <= 0:
        return None
    return avg_recent / avg_base


def match_ma_bull(series: BarSeries) -> PatternMatch | None:
    """均线多头排列：MA5>MA10>MA20>MA60 且现价站上 MA20。"""
    if len(series.closes) < 60:
        return None
    ma5 = _ma(series.closes, 5)
    ma10 = _ma(series.closes, 10)
    ma20 = _ma(series.closes, 20)
    ma60 = _ma(series.closes, 60)
    if ma5 is None or ma10 is None or ma20 is None or ma60 is None:
        return None
    if not (ma5 > ma10 > ma20 > ma60):
        return None
    last = series.closes[-1]
    if last < ma20:
        return None
    ret20 = 0.0
    if len(series.closes) >= 21 and series.closes[-21] > 0:
        ret20 = (last - series.closes[-21]) / series.closes[-21] * 100
    spread = (ma5 - ma60) / ma60 * 100 if ma60 else 0.0
    vol_ratio = _volume_ratio(series.volumes) or 1.0
    score = ret20 + spread + min(vol_ratio, 3.0) * 2
    return PatternMatch(
        score=round(score, 2),
        hint=f"MA5>MA10>MA20>MA60，20日涨幅 {ret20:.1f}%",
    )


def _local_minima(values: list[float], *, radius: int = 2) -> list[int]:
    mins: list[int] = []
    for index in range(radius, len(values) - radius):
        window = values[index - radius : index + radius + 1]
        if values[index] <= min(window):
            mins.append(index)
    return mins


def match_w_bottom(series: BarSeries) -> PatternMatch | None:
    """W 底：双底结构 + 近端突破颈线（简化）。"""
    if len(series.closes) < 60:
        return None
    lows = series.lows[-60:]
    closes = series.closes[-60:]
    mins = _local_minima(lows)
    if len(mins) < 2:
        return None

    best: PatternMatch | None = None
    for left in range(len(mins) - 1):
        i, j = mins[left], mins[left + 1]
        if j - i < 8:
            continue
        low1, low2 = lows[i], lows[j]
        if low1 <= 0 or low2 <= 0:
            continue
        if abs(low2 - low1) / low1 > 0.06:
            continue
        peak = max(series.highs[-60:][i : j + 1])
        neckline = peak
        if closes[-1] < neckline * 0.99:
            continue
        depth = (neckline - min(low1, low2)) / neckline * 100
        breakout = (closes[-1] - neckline) / neckline * 100
        score = depth + breakout * 2
        hint = f"双底相近，颈线约 {neckline:.2f}，突破 {breakout:.1f}%"
        candidate = PatternMatch(score=round(score, 2), hint=hint)
        if best is None or candidate.score > best.score:
            best = candidate
    return best


def _ma_series(closes: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for index in range(len(closes)):
        if index + 1 < window:
            out.append(None)
            continue
        segment = closes[index + 1 - window : index + 1]
        out.append(sum(segment) / len(segment))
    return out


def match_old_duck(series: BarSeries) -> PatternMatch | None:
    """老鸭头（简化）：中期多头 + 近期 MA5 金叉 MA10 + 放量上攻。"""
    if len(series.closes) < 80:
        return None
    closes = series.closes[-80:]
    ma5s = _ma_series(closes, 5)
    ma10s = _ma_series(closes, 10)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    if ma20 is None or ma60 is None or ma10s[-1] is None or ma5s[-1] is None:
        return None
    if not (ma10s[-1] > ma20 > ma60):
        return None

    cross_index = None
    for index in range(len(closes) - 15, len(closes)):
        if index < 1:
            continue
        prev5, cur5 = ma5s[index - 1], ma5s[index]
        prev10, cur10 = ma10s[index - 1], ma10s[index]
        if prev5 is None or cur5 is None or prev10 is None or cur10 is None:
            continue
        if prev5 <= prev10 and cur5 > cur10:
            cross_index = index
            break
    if cross_index is None:
        return None

    before = cross_index - 5
    if before < 5:
        return None
    had_below = False
    for index in range(before - 5, before):
        v5, v10 = ma5s[index], ma10s[index]
        if v5 is not None and v10 is not None and v5 < v10:
            had_below = True
            break
    if not had_below:
        return None

    pullback_low = min(closes[max(0, cross_index - 20) : cross_index])
    if pullback_low < ma60 * 0.97:
        return None

    vol_ratio = _volume_ratio(series.volumes, recent=5, base=20)
    if vol_ratio is None or vol_ratio < 1.05:
        return None
    if closes[-1] < (ma5s[-1] or 0):
        return None

    score = vol_ratio * 10 + (closes[-1] - ma60) / ma60 * 100
    return PatternMatch(
        score=round(score, 2),
        hint=f"MA5 上穿 MA10，5日量比 {vol_ratio:.2f}",
    )


PATTERN_MATCHERS = {
    "ma_bull": match_ma_bull,
    "old_duck": match_old_duck,
    "w_bottom": match_w_bottom,
}
