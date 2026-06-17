"""策略信号纯函数（与 CTA 策略逻辑对齐，不依赖回测引擎）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

SignalType = Literal["golden_cross", "death_cross"]


@dataclass(frozen=True)
class CrossSignal:
    signal_type: SignalType
    bar_date: str
    close: float
    fast_ma: float
    slow_ma: float


def _sma(values: list[float], window: int, end_index: int) -> float | None:
    if end_index + 1 < window:
        return None
    segment = values[end_index + 1 - window : end_index + 1]
    return sum(segment) / len(segment)


def compute_double_ma_crosses(
    closes: list[float],
    dates: list[date | datetime],
    *,
    fast_window: int = 10,
    slow_window: int = 20,
) -> list[CrossSignal]:
    """扫描全序列，返回金叉/死叉事件（与 AshareDoubleMaStrategy 判定一致）。"""
    if fast_window >= slow_window:
        raise ValueError("fast_window 必须小于 slow_window")
    if len(closes) != len(dates):
        raise ValueError("closes 与 dates 长度不一致")
    if len(closes) < slow_window + 2:
        return []

    signals: list[CrossSignal] = []
    for index in range(slow_window + 1, len(closes)):
        fast_ma0 = _sma(closes, fast_window, index)
        fast_ma1 = _sma(closes, fast_window, index - 1)
        slow_ma0 = _sma(closes, slow_window, index)
        slow_ma1 = _sma(closes, slow_window, index - 1)
        if None in (fast_ma0, fast_ma1, slow_ma0, slow_ma1):
            continue

        cross_over = fast_ma0 > slow_ma0 and fast_ma1 <= slow_ma1
        cross_below = fast_ma0 < slow_ma0 and fast_ma1 >= slow_ma1
        bar_dt = dates[index]
        bar_date = bar_dt.strftime("%Y-%m-%d") if isinstance(bar_dt, datetime) else bar_dt.isoformat()
        close = round(closes[index], 2)

        if cross_over:
            signals.append(
                CrossSignal(
                    signal_type="golden_cross",
                    bar_date=bar_date,
                    close=close,
                    fast_ma=round(fast_ma0, 2),
                    slow_ma=round(slow_ma0, 2),
                )
            )
        elif cross_below:
            signals.append(
                CrossSignal(
                    signal_type="death_cross",
                    bar_date=bar_date,
                    close=close,
                    fast_ma=round(fast_ma0, 2),
                    slow_ma=round(slow_ma0, 2),
                )
            )
    return signals


def summarize_double_ma_state(
    closes: list[float],
    dates: list[date | datetime],
    *,
    fast_window: int = 10,
    slow_window: int = 20,
    recent_limit: int = 5,
) -> dict[str, Any]:
    """汇总当前均线状态与最近交叉信号。"""
    if len(closes) < slow_window + 2:
        return {
            "error": "K 线数量不足，无法计算双均线信号",
            "min_bars": slow_window + 2,
            "bars_available": len(closes),
        }

    last_index = len(closes) - 1
    fast_ma0 = _sma(closes, fast_window, last_index)
    fast_ma1 = _sma(closes, fast_window, last_index - 1)
    slow_ma0 = _sma(closes, slow_window, last_index)
    _ = _sma(closes, slow_window, last_index - 1)
    assert fast_ma0 is not None and slow_ma0 is not None

    if fast_ma0 > slow_ma0:
        alignment = "快线在慢线上方（多头均线排列）"
    elif fast_ma0 < slow_ma0:
        alignment = "快线在慢线下方（空头均线排列）"
    else:
        alignment = "快线与慢线重合"

    last_dt = dates[last_index]
    as_of = last_dt.strftime("%Y-%m-%d") if isinstance(last_dt, datetime) else last_dt.isoformat()

    crosses = compute_double_ma_crosses(
        closes,
        dates,
        fast_window=fast_window,
        slow_window=slow_window,
    )
    last_cross = crosses[-1] if crosses else None
    recent = crosses[-recent_limit:] if crosses else []

    last_cross_payload: dict[str, Any] | None = None
    if last_cross is not None:
        last_cross_payload = {
            "type": last_cross.signal_type,
            "type_label": "金叉" if last_cross.signal_type == "golden_cross" else "死叉",
            "date": last_cross.bar_date,
            "close": last_cross.close,
            "fast_ma": last_cross.fast_ma,
            "slow_ma": last_cross.slow_ma,
        }

    return {
        "as_of": as_of,
        "last_close": round(closes[last_index], 2),
        "params": {"fast_window": fast_window, "slow_window": slow_window},
        "current": {
            "fast_ma": round(fast_ma0, 2),
            "slow_ma": round(slow_ma0, 2),
            "alignment": alignment,
            "fast_slope": round(fast_ma0 - (fast_ma1 or fast_ma0), 4),
        },
        "last_cross": last_cross_payload,
        "recent_signals": [
            {
                "type": item.signal_type,
                "type_label": "金叉" if item.signal_type == "golden_cross" else "死叉",
                "date": item.bar_date,
                "close": item.close,
                "fast_ma": item.fast_ma,
                "slow_ma": item.slow_ma,
            }
            for item in recent
        ],
        "signal_count": len(crosses),
    }


SUPPORTED_SIGNAL_STRATEGIES: dict[str, str] = {
    "AshareDoubleMaStrategy": "double_ma",
    "AshareShortBreakoutStrategy": "short_breakout",
    "AshareSwingMaStrategy": "swing_ma",
    "AshareTrendMaStrategy": "trend_ma",
    "AshareLimitBoardStrategy": "limit_board",
    "AshareIntradayBreakoutStrategy": "intraday_breakout",
    "AsharePullbackStrategy": "pullback",
}

STRATEGY_SIGNAL_DEFAULTS: dict[str, tuple[int, int]] = {
    "AshareDoubleMaStrategy": (10, 20),
    "AshareShortBreakoutStrategy": (5, 10),
    "AshareSwingMaStrategy": (10, 20),
    "AshareTrendMaStrategy": (20, 60),
    "AshareLimitBoardStrategy": (5, 10),
    "AshareIntradayBreakoutStrategy": (5, 10),
    "AsharePullbackStrategy": (5, 10),
}

STRATEGY_SIGNAL_RECENT_DAYS: dict[str, int] = {
    "AshareDoubleMaStrategy": 5,
    "AshareShortBreakoutStrategy": 2,
    "AshareSwingMaStrategy": 5,
    "AshareTrendMaStrategy": 15,
    "AshareLimitBoardStrategy": 1,
    "AshareIntradayBreakoutStrategy": 1,
    "AsharePullbackStrategy": 2,
}


def list_supported_signal_strategies() -> list[str]:
    return sorted(SUPPORTED_SIGNAL_STRATEGIES.keys())


def _parse_bar_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_between(later: str, earlier: str) -> int | None:
    end = _parse_bar_date(later)
    start = _parse_bar_date(earlier)
    if end is None or start is None:
        return None
    return (end - start).days


def classify_double_ma_signal(
    state: dict[str, Any],
    *,
    recent_days: int = 5,
) -> Literal["buy", "sell", "hold", "na"]:
    """双均线信号状态（与 AshareDoubleMaStrategy 交叉事件对齐）。"""
    if state.get("error"):
        return "na"

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    if fast_ma is None or slow_ma is None:
        return "na"

    as_of = str(state.get("as_of") or "")
    last_cross = state.get("last_cross")
    if not last_cross or not as_of:
        return "hold"

    cross_date = str(last_cross.get("date") or "")
    elapsed = _days_between(as_of, cross_date)
    if elapsed is None or elapsed > max(0, int(recent_days)):
        return "hold"

    cross_type = last_cross.get("type")
    if cross_type == "golden_cross" and fast_ma > slow_ma:
        return "buy"
    if cross_type == "death_cross" and fast_ma < slow_ma:
        return "sell"
    return "hold"


def build_double_ma_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
    recent_days: int = 5,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> dict[str, Any]:
    """汇总双均线 + 综合技术面信号快照（供 UI / AnalysisService 使用）。"""
    return build_composite_signal_payload(
        closes,
        dates,
        vt_symbol=vt_symbol,
        strategy_id=strategy_id,
        fast_window=fast_window,
        slow_window=slow_window,
        recent_days=recent_days,
        highs=highs,
        lows=lows,
        volumes=volumes,
    )


def _sma_at(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    segment = values[-window:]
    return round(sum(segment) / len(segment), 2)


def _volume_ratio_5d(volumes: list[float]) -> float | None:
    if len(volumes) < 10:
        return None
    recent = volumes[-5:]
    base = volumes[-10:-5]
    avg_recent = sum(recent) / len(recent)
    avg_base = sum(base) / len(base)
    if avg_base <= 0:
        return None
    return round(avg_recent / avg_base, 2)


def _ma_signal_score(signal: Literal["buy", "sell", "hold", "na"]) -> float:
    return {"buy": 80.0, "sell": 80.0, "hold": 40.0, "na": 0.0}[signal]


def _alignment_score(
    *,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    last_close: float,
) -> float:
    if ma5 is None or ma10 is None or ma20 is None:
        return 30.0
    if ma5 > ma10 > ma20:
        return 90.0 if last_close >= ma20 else 70.0
    if ma5 < ma10 < ma20:
        return 15.0
    return 50.0


def _volume_score(volume_ratio: float | None) -> float:
    if volume_ratio is None:
        return 50.0
    if volume_ratio > 1.5:
        return 80.0
    if volume_ratio >= 0.8:
        return 50.0
    return 20.0


def _pattern_score(closes: list[float], highs: list[float], lows: list[float], volumes: list[float]) -> float:
    del highs, lows, volumes
    return 90.0 if _is_ma_bull_pattern(closes) else 30.0


def _is_ma_bull_pattern(closes: list[float]) -> bool:
    """均线多头排列：MA5>MA10>MA20>MA60 且现价站上 MA20。"""
    if len(closes) < 60:
        return False
    ma5 = _sma_at(closes, 5)
    ma10 = _sma_at(closes, 10)
    ma20 = _sma_at(closes, 20)
    ma60 = _sma_at(closes, 60)
    if None in (ma5, ma10, ma20, ma60):
        return False
    if not (ma5 > ma10 > ma20 > ma60):
        return False
    return closes[-1] >= ma20


def classify_composite_signal(
    state: dict[str, Any],
    *,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    last_close: float,
    volume_ratio: float | None,
    recent_days: int = 5,
) -> Literal["buy", "sell", "hold", "na"]:
    """综合技术面信号（Phase A 双均线 + 均线排列 + 量比）。"""
    base = classify_double_ma_signal(state, recent_days=recent_days)
    if base == "na":
        return "na"
    if base in ("buy", "sell"):
        return base
    if ma5 is not None and ma10 is not None and ma20 is not None:
        if ma5 > ma10 > ma20 and volume_ratio is not None and volume_ratio >= 1.2 and last_close >= ma20:
            return "buy"
        if ma5 < ma10 < ma20 and last_close < ma20:
            return "sell"
    return "hold"


def _compute_ref_prices(
    state: dict[str, Any],
    highs: list[float],
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    fast_window: int,
    slow_window: int,
    lookback_high: int = 20,
) -> tuple[float | None, float | None]:
    """按信号态返回支撑/阻力锚点（均线参考，非实时买卖价）。"""
    if signal == "na":
        return None, None

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    last_cross = state.get("last_cross") or {}
    recent_high = max(highs[-lookback_high:]) if len(highs) >= 1 else None

    if signal == "buy":
        ref_buy = slow_ma
        if last_cross.get("type") == "golden_cross":
            cross_close = last_cross.get("close")
            if isinstance(cross_close, (int, float)) and slow_ma is not None:
                ref_buy = round(min(float(slow_ma), float(cross_close)), 2)
            elif isinstance(cross_close, (int, float)):
                ref_buy = round(float(cross_close), 2)
        ref_sell = fast_ma
        if fast_ma is not None and recent_high is not None:
            ref_sell = round(min(float(recent_high), float(fast_ma) * 1.05), 2)
        elif recent_high is not None:
            ref_sell = round(float(recent_high), 2)
        return ref_buy, ref_sell

    if signal == "sell":
        ref_buy = round(float(slow_ma), 2) if slow_ma is not None else None
        ref_sell = fast_ma
        if fast_ma is not None and recent_high is not None:
            ref_sell = round(min(float(recent_high), float(fast_ma)), 2)
        elif recent_high is not None:
            ref_sell = round(float(recent_high), 2)
        return ref_buy, ref_sell

    ref_buy = round(float(slow_ma), 2) if slow_ma is not None else None
    ref_sell = round(float(fast_ma), 2) if fast_ma is not None else None
    return ref_buy, ref_sell


def _compute_action_ref_prices(
    state: dict[str, Any],
    highs: list[float],
    lows: list[float],
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    last_close: float,
    fast_window: int,
    slow_window: int,
    lookback: int = 20,
) -> tuple[float | None, float | None]:
    """按信号态返回入场/离场动作参考价（与结构锚点独立）。"""
    if signal == "na":
        return None, None

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    last_cross = state.get("last_cross") or {}
    recent_high = max(highs[-lookback:]) if highs else None
    recent_low = min(lows[-lookback:]) if lows else None

    if signal == "buy":
        candidates: list[float] = [last_close]
        if slow_ma is not None:
            candidates.append(float(slow_ma))
        if last_cross.get("type") == "golden_cross":
            cross_close = last_cross.get("close")
            if isinstance(cross_close, (int, float)):
                candidates.append(float(cross_close))
        action_buy = round(min(candidates), 2)
        action_sell = fast_ma
        if fast_ma is not None and recent_high is not None:
            action_sell = round(min(float(recent_high), float(fast_ma) * 1.05), 2)
        elif recent_high is not None:
            action_sell = round(float(recent_high), 2)
        return action_buy, action_sell

    if signal == "sell":
        action_buy = None
        if recent_low is not None:
            action_buy = round(min(recent_low, last_close * 0.98), 2)
        elif last_close > 0:
            action_buy = round(last_close * 0.98, 2)
        action_sell = round(last_close, 2)
        if fast_ma is not None:
            action_sell = round(max(last_close, float(fast_ma)), 2)
        return action_buy, action_sell

    action_buy = None
    if slow_ma is not None:
        action_buy = round(min(float(slow_ma), last_close), 2)
    action_sell = None
    if fast_ma is not None:
        action_sell = round(max(float(fast_ma), last_close), 2)
    return action_buy, action_sell


def _ref_price_reason_lines(
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    ref_buy: float | None,
    ref_sell: float | None,
    fast_window: int,
    slow_window: int,
) -> list[str]:
    lines: list[str] = []
    if ref_buy is not None:
        if signal == "buy":
            lines.append(f"支撑锚点：MA{slow_window} 入场结构 = {ref_buy}")
        elif signal == "sell":
            lines.append(f"支撑锚点：MA{slow_window} 跌破结构 = {ref_buy}")
        else:
            lines.append(f"支撑锚点：MA{slow_window} = {ref_buy}")
    if ref_sell is not None:
        if signal == "buy":
            lines.append(f"阻力锚点：MA{fast_window} 上方阻力 ≤ {ref_sell}")
        elif signal == "sell":
            lines.append(f"阻力锚点：MA{fast_window} 反弹阻力 = {ref_sell}")
        else:
            lines.append(f"阻力锚点：MA{fast_window} = {ref_sell}")
    return lines


def _action_ref_reason_lines(
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    action_buy: float | None,
    action_sell: float | None,
    fast_window: int,
    slow_window: int,
) -> list[str]:
    lines: list[str] = []
    if action_buy is not None:
        if signal == "buy":
            lines.append(f"参考买价：min(金叉/慢{slow_window}/收盘) 低吸入场 = {action_buy}")
        elif signal == "sell":
            lines.append(f"参考买价：近低回补参考 = {action_buy}")
        else:
            lines.append(f"参考买价：回踩关注 min(慢{slow_window}/收盘) = {action_buy}")
    if action_sell is not None:
        if signal == "buy":
            lines.append(f"参考卖价：止盈阻力参考 ≤ {action_sell}")
        elif signal == "sell":
            lines.append(f"参考卖价：max(收盘/快{fast_window}) 离场参考 = {action_sell}")
        else:
            lines.append(f"参考卖价：反弹关注 max(快{fast_window}/收盘) = {action_sell}")
    return lines


def _build_reason_summary(
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    state: dict[str, Any],
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    volume_ratio: float | None,
    pattern_hit: bool,
) -> str:
    tags: list[str] = []
    last_cross = state.get("last_cross") or {}
    if last_cross.get("type_label"):
        tags.append(str(last_cross["type_label"]))
    if ma5 is not None and ma10 is not None and ma20 is not None:
        if ma5 > ma10 > ma20:
            tags.append("多头")
        elif ma5 < ma10 < ma20:
            tags.append("空头")
    if volume_ratio is not None:
        tags.append(f"量比{volume_ratio:.1f}")
    if pattern_hit:
        tags.append("均线多头")
    if not tags:
        labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
        return labels[signal]
    return "+".join(tags)


def _compute_strength(
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    alignment: float,
    volume: float,
    pattern: float,
) -> float:
    score = 0.40 * _ma_signal_score(signal) + 0.25 * alignment + 0.20 * volume + 0.15 * pattern
    return round(max(0.0, min(score, 100.0)), 1)


def build_composite_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
    recent_days: int = 5,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> dict[str, Any]:
    """综合技术面信号快照。"""
    state = summarize_double_ma_state(
        closes,
        dates,
        fast_window=fast_window,
        slow_window=slow_window,
    )
    warnings: list[str] = []
    if state.get("error"):
        warnings.append(str(state["error"]))
        return {
            "vt_symbol": vt_symbol,
            "strategy_id": strategy_id,
            "as_of": "",
            "signal": "na",
            "signal_label": "—",
            "signal_date": None,
            "ref_buy_price": None,
            "ref_sell_price": None,
            "action_ref_buy_price": None,
            "action_ref_sell_price": None,
            "strength": None,
            "reason_summary": "",
            "reasons": (),
            "warnings": tuple(warnings),
            "last_close": None,
        }

    high_series = highs if highs is not None else closes
    low_series = lows if lows is not None else closes
    vol_series = volumes if volumes is not None else []
    last_close = round(closes[-1], 2)
    ma5 = _sma_at(closes, 5)
    ma10 = _sma_at(closes, 10)
    ma20 = _sma_at(closes, 20)
    volume_ratio = _volume_ratio_5d(vol_series) if vol_series else None

    signal = classify_composite_signal(
        state,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        last_close=last_close,
        volume_ratio=volume_ratio,
        recent_days=recent_days,
    )
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
    last_cross = state.get("last_cross") or {}
    signal_date = last_cross.get("date") if signal in ("buy", "sell") else None
    ref_buy, ref_sell = _compute_ref_prices(
        state,
        high_series,
        signal=signal,
        fast_window=fast_window,
        slow_window=slow_window,
    )
    action_buy, action_sell = _compute_action_ref_prices(
        state,
        high_series,
        low_series,
        signal=signal,
        last_close=last_close,
        fast_window=fast_window,
        slow_window=slow_window,
    )

    pattern_hit = _is_ma_bull_pattern(closes)

    align_score = _alignment_score(ma5=ma5, ma10=ma10, ma20=ma20, last_close=last_close)
    vol_score = _volume_score(volume_ratio)
    pat_score = 90.0 if pattern_hit else 30.0
    cross_score = _ma_signal_score(signal)
    strength = _compute_strength(
        signal=signal,
        alignment=align_score,
        volume=vol_score,
        pattern=pat_score,
    )
    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    ma_gap_pct: float | None = None
    if isinstance(fast_ma, (int, float)) and isinstance(slow_ma, (int, float)) and float(slow_ma) > 0:
        ma_gap_pct = round((float(fast_ma) - float(slow_ma)) / float(slow_ma) * 100, 2)
    reason_summary = _build_reason_summary(
        signal=signal,
        state=state,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        volume_ratio=volume_ratio,
        pattern_hit=pattern_hit,
    )

    reasons: list[str] = []
    alignment = (state.get("current") or {}).get("alignment")
    if alignment:
        reasons.append(str(alignment))
    if last_cross:
        cross_label = last_cross.get("type_label") or last_cross.get("type")
        cross_day = last_cross.get("date")
        if cross_label and cross_day:
            reasons.append(f"最近交叉：{cross_label}（{cross_day}）")
    if reason_summary:
        reasons.append(f"综合：{reason_summary}")
    reasons.extend(
        _ref_price_reason_lines(
            signal=signal,
            ref_buy=ref_buy,
            ref_sell=ref_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.extend(
        _action_ref_reason_lines(
            signal=signal,
            action_buy=action_buy,
            action_sell=action_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.append(f"强度：{strength:.0f}")

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": str(state.get("as_of") or ""),
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": signal_date,
        "ref_buy_price": ref_buy,
        "ref_sell_price": ref_sell,
        "action_ref_buy_price": action_buy,
        "action_ref_sell_price": action_sell,
        "strength": strength,
        "reason_summary": reason_summary,
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": round(closes[-1], 2),
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "volume_ratio_5d": volume_ratio,
        "ma_gap_pct": ma_gap_pct,
        "strength_cross": cross_score,
        "strength_alignment": align_score,
        "strength_volume": vol_score,
        "strength_pattern": pat_score,
    }


@dataclass(frozen=True)
class BreakoutEvent:
    bar_date: str
    close: float
    breakout_level: float
    volume_ratio: float
    fast_ma: float
    slow_ma: float


def _high_max(values: list[float], end_index: int, lookback: int) -> float | None:
    if end_index < lookback:
        return None
    segment = values[end_index - lookback : end_index]
    if not segment:
        return None
    return max(segment)


def compute_breakout_events(
    closes: list[float],
    highs: list[float],
    dates: list[date | datetime],
    volumes: list[float],
    *,
    fast_window: int = 5,
    slow_window: int = 10,
    breakout_lookback: int = 5,
    volume_ratio_min: float = 1.5,
) -> list[BreakoutEvent]:
    """扫描放量突破事件（与 AshareShortBreakoutStrategy 判定一致）。"""
    if len({len(closes), len(highs), len(dates), len(volumes)}) != 1:
        raise ValueError("closes/highs/dates/volumes 长度须一致")
    min_bars = max(slow_window, breakout_lookback) + 2
    if len(closes) < min_bars:
        return []

    events: list[BreakoutEvent] = []
    for index in range(min_bars - 1, len(closes)):
        fast_ma0 = _sma(closes, fast_window, index)
        slow_ma0 = _sma(closes, slow_window, index)
        breakout_level = _high_max(highs, index, breakout_lookback)
        if None in (fast_ma0, slow_ma0, breakout_level):
            continue

        vol_ratio = _volume_ratio_at(volumes, index)
        if vol_ratio is None or vol_ratio < volume_ratio_min:
            continue
        if closes[index] <= breakout_level or fast_ma0 <= slow_ma0:
            continue

        bar_dt = dates[index]
        bar_date = bar_dt.strftime("%Y-%m-%d") if isinstance(bar_dt, datetime) else bar_dt.isoformat()
        events.append(
            BreakoutEvent(
                bar_date=bar_date,
                close=round(closes[index], 2),
                breakout_level=round(float(breakout_level), 2),
                volume_ratio=round(vol_ratio, 2),
                fast_ma=round(fast_ma0, 2),
                slow_ma=round(slow_ma0, 2),
            )
        )
    return events


def _volume_ratio_at(volumes: list[float], end_index: int, window: int = 5) -> float | None:
    if end_index + 1 < window * 2:
        return None
    recent = volumes[end_index + 1 - window : end_index + 1]
    base = volumes[end_index + 1 - window * 2 : end_index + 1 - window]
    avg_recent = sum(recent) / len(recent)
    avg_base = sum(base) / len(base)
    if avg_base <= 0:
        return None
    return avg_recent / avg_base


def summarize_short_breakout_state(
    closes: list[float],
    highs: list[float],
    dates: list[date | datetime],
    volumes: list[float],
    *,
    fast_window: int = 5,
    slow_window: int = 10,
    breakout_lookback: int = 5,
    volume_ratio_min: float = 1.5,
    recent_limit: int = 5,
) -> dict[str, Any]:
    """汇总短线突破状态与最近事件。"""
    min_bars = max(slow_window, breakout_lookback) + 2
    if len(closes) < min_bars:
        return {
            "error": "K 线数量不足，无法计算短线突破信号",
            "min_bars": min_bars,
            "bars_available": len(closes),
        }

    last_index = len(closes) - 1
    fast_ma0 = _sma(closes, fast_window, last_index)
    slow_ma0 = _sma(closes, slow_window, last_index)
    assert fast_ma0 is not None and slow_ma0 is not None

    last_dt = dates[last_index]
    as_of = last_dt.strftime("%Y-%m-%d") if isinstance(last_dt, datetime) else last_dt.isoformat()
    volume_ratio = _volume_ratio_at(volumes, last_index)
    breakout_level = _high_max(highs, last_index, breakout_lookback)

    if fast_ma0 > slow_ma0:
        alignment = "快线在慢线上方（多头均线排列）"
    elif fast_ma0 < slow_ma0:
        alignment = "快线在慢线下方（空头均线排列）"
    else:
        alignment = "快线与慢线重合"

    ma_state = summarize_double_ma_state(
        closes,
        dates,
        fast_window=fast_window,
        slow_window=slow_window,
        recent_limit=recent_limit,
    )
    breakouts = compute_breakout_events(
        closes,
        highs,
        dates,
        volumes,
        fast_window=fast_window,
        slow_window=slow_window,
        breakout_lookback=breakout_lookback,
        volume_ratio_min=volume_ratio_min,
    )
    last_breakout = breakouts[-1] if breakouts else None
    last_cross = ma_state.get("last_cross")

    last_breakout_payload: dict[str, Any] | None = None
    if last_breakout is not None:
        last_breakout_payload = {
            "type": "breakout",
            "type_label": "放量突破",
            "date": last_breakout.bar_date,
            "close": last_breakout.close,
            "breakout_level": last_breakout.breakout_level,
            "volume_ratio": last_breakout.volume_ratio,
            "fast_ma": last_breakout.fast_ma,
            "slow_ma": last_breakout.slow_ma,
        }

    return {
        "as_of": as_of,
        "last_close": round(closes[last_index], 2),
        "params": {
            "fast_window": fast_window,
            "slow_window": slow_window,
            "breakout_lookback": breakout_lookback,
            "volume_ratio_min": volume_ratio_min,
        },
        "current": {
            "fast_ma": round(fast_ma0, 2),
            "slow_ma": round(slow_ma0, 2),
            "alignment": alignment,
            "volume_ratio": volume_ratio,
            "breakout_level": round(breakout_level, 2) if breakout_level is not None else None,
        },
        "last_breakout": last_breakout_payload,
        "last_cross": last_cross,
        "recent_breakouts": [
            {
                "type": "breakout",
                "type_label": "放量突破",
                "date": item.bar_date,
                "close": item.close,
                "breakout_level": item.breakout_level,
                "volume_ratio": item.volume_ratio,
            }
            for item in breakouts[-recent_limit:]
        ],
        "breakout_count": len(breakouts),
    }


def classify_short_breakout_signal(
    state: dict[str, Any],
    *,
    recent_days: int = 2,
) -> Literal["buy", "sell", "hold", "na"]:
    """短线突破信号（突破买入 / 死叉卖出）。"""
    if state.get("error"):
        return "na"

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    if fast_ma is None or slow_ma is None:
        return "na"

    as_of = str(state.get("as_of") or "")
    last_cross = state.get("last_cross")
    if last_cross and as_of:
        cross_date = str(last_cross.get("date") or "")
        elapsed = _days_between(as_of, cross_date)
        if elapsed is not None and elapsed <= max(0, int(recent_days)) and last_cross.get("type") == "death_cross" and fast_ma < slow_ma:
            return "sell"

    last_breakout = state.get("last_breakout")
    if not last_breakout or not as_of:
        return "hold"

    elapsed = _days_between(as_of, str(last_breakout.get("date") or ""))
    if elapsed is None or elapsed > max(0, int(recent_days)):
        return "hold"

    if fast_ma > slow_ma:
        return "buy"
    return "hold"


def _short_breakout_strength(
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    volume_ratio: float | None,
    breakout_level: float | None,
    last_close: float,
) -> tuple[float, float, float, float]:
    cross_score = _ma_signal_score(signal)
    vol_score = _volume_score(volume_ratio)
    breakout_score = 50.0
    if breakout_level is not None and breakout_level > 0 and signal == "buy":
        pct = (last_close - breakout_level) / breakout_level * 100
        breakout_score = min(90.0, 60.0 + pct * 5.0)
    strength = 0.30 * cross_score + 0.40 * vol_score + 0.30 * breakout_score
    return round(strength, 1), cross_score, vol_score, breakout_score


def build_short_breakout_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareShortBreakoutStrategy",
    fast_window: int = 5,
    slow_window: int = 10,
    breakout_lookback: int = 5,
    volume_ratio_min: float = 1.5,
    recent_days: int = 2,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> dict[str, Any]:
    """短线放量突破信号快照。"""
    high_series = highs if highs is not None else closes
    low_series = lows if lows is not None else closes
    vol_series = volumes if volumes is not None else []
    state = summarize_short_breakout_state(
        closes,
        high_series,
        dates,
        vol_series,
        fast_window=fast_window,
        slow_window=slow_window,
        breakout_lookback=breakout_lookback,
        volume_ratio_min=volume_ratio_min,
    )
    warnings: list[str] = []
    if state.get("error"):
        warnings.append(str(state["error"]))
        return {
            "vt_symbol": vt_symbol,
            "strategy_id": strategy_id,
            "as_of": "",
            "signal": "na",
            "signal_label": "—",
            "signal_date": None,
            "ref_buy_price": None,
            "ref_sell_price": None,
            "action_ref_buy_price": None,
            "action_ref_sell_price": None,
            "strength": None,
            "reason_summary": "",
            "reasons": (),
            "warnings": tuple(warnings),
            "last_close": None,
        }

    last_close = round(closes[-1], 2)
    current = state.get("current") or {}
    volume_ratio = current.get("volume_ratio")
    breakout_level = current.get("breakout_level")
    signal = classify_short_breakout_signal(state, recent_days=recent_days)
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}

    ma_state = summarize_double_ma_state(closes, dates, fast_window=fast_window, slow_window=slow_window)
    last_breakout = state.get("last_breakout") or {}
    last_cross = state.get("last_cross") or {}
    signal_date = None
    if signal == "buy":
        signal_date = last_breakout.get("date")
    elif signal == "sell":
        signal_date = last_cross.get("date")

    ref_buy = current.get("breakout_level") or current.get("slow_ma")
    ref_sell = current.get("fast_ma")
    if isinstance(ref_buy, (int, float)):
        ref_buy = round(float(ref_buy), 2)
    if isinstance(ref_sell, (int, float)):
        ref_sell = round(float(ref_sell), 2)

    action_buy, action_sell = _compute_action_ref_prices(
        ma_state,
        high_series,
        low_series,
        signal=signal,
        last_close=last_close,
        fast_window=fast_window,
        slow_window=slow_window,
    )

    strength, cross_score, vol_score, breakout_score = _short_breakout_strength(
        signal=signal,
        volume_ratio=volume_ratio if isinstance(volume_ratio, (int, float)) else None,
        breakout_level=breakout_level if isinstance(breakout_level, (int, float)) else None,
        last_close=last_close,
    )

    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    ma_gap_pct: float | None = None
    if isinstance(fast_ma, (int, float)) and isinstance(slow_ma, (int, float)) and float(slow_ma) > 0:
        ma_gap_pct = round((float(fast_ma) - float(slow_ma)) / float(slow_ma) * 100, 2)

    tags: list[str] = []
    if last_breakout.get("type_label"):
        tags.append(str(last_breakout["type_label"]))
    if volume_ratio is not None:
        tags.append(f"量比{float(volume_ratio):.1f}")
    if breakout_level is not None:
        tags.append(f"突破{float(breakout_level):.2f}")
    reason_summary = "+".join(tags) if tags else labels[signal]

    reasons: list[str] = []
    alignment = current.get("alignment")
    if alignment:
        reasons.append(str(alignment))
    if last_breakout.get("type_label") and last_breakout.get("date"):
        reasons.append(f"最近突破：{last_breakout['type_label']}（{last_breakout['date']}） 量比 {last_breakout.get('volume_ratio', '—')}")
    if last_cross.get("type_label") and last_cross.get("date"):
        reasons.append(f"最近交叉：{last_cross['type_label']}（{last_cross['date']}）")
    reasons.append(f"综合：{reason_summary}")
    reasons.extend(
        _ref_price_reason_lines(
            signal=signal,
            ref_buy=ref_buy,
            ref_sell=ref_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.extend(
        _action_ref_reason_lines(
            signal=signal,
            action_buy=action_buy,
            action_sell=action_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.append(f"强度：{strength:.0f}")

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": str(state.get("as_of") or ""),
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": signal_date,
        "ref_buy_price": ref_buy,
        "ref_sell_price": ref_sell,
        "action_ref_buy_price": action_buy,
        "action_ref_sell_price": action_sell,
        "strength": strength,
        "reason_summary": reason_summary,
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": last_close,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "volume_ratio_5d": volume_ratio,
        "ma_gap_pct": ma_gap_pct,
        "strength_cross": cross_score,
        "strength_alignment": breakout_score,
        "strength_volume": vol_score,
        "strength_pattern": None,
    }


@dataclass(frozen=True)
class PullbackEntry:
    bar_date: str
    close: float
    fast_ma: float
    slow_ma: float
    volume_ratio: float


def _volume_shrink_at(volumes: list[float], end_index: int, window: int = 5) -> bool:
    """当日量低于前 window 日均量（与 AshareSwingMaStrategy._is_pullback 一致）。"""
    if end_index < window:
        return False
    base = volumes[end_index - window : end_index]
    avg_base = sum(base) / len(base)
    if avg_base <= 0:
        return True
    return volumes[end_index] < avg_base


def compute_swing_pullback_entries(
    closes: list[float],
    lows: list[float],
    dates: list[date | datetime],
    volumes: list[float],
    *,
    fast_window: int = 10,
    slow_window: int = 20,
    pullback_pct: float = 2.0,
    pullback_wait_days: int = 5,
) -> list[PullbackEntry]:
    """扫描金叉后缩量回踩慢线入场事件（与 AshareSwingMaStrategy 一致）。"""
    if len({len(closes), len(lows), len(dates), len(volumes)}) != 1:
        raise ValueError("closes/lows/dates/volumes 长度须一致")

    crosses = compute_double_ma_crosses(
        closes,
        dates,
        fast_window=fast_window,
        slow_window=slow_window,
    )
    if not crosses:
        return []

    date_to_index = {}
    for index, bar_dt in enumerate(dates):
        key = bar_dt.strftime("%Y-%m-%d") if isinstance(bar_dt, datetime) else bar_dt.isoformat()
        date_to_index[key] = index

    band = pullback_pct / 100.0
    entries: list[PullbackEntry] = []
    for cross in crosses:
        if cross.signal_type != "golden_cross":
            continue
        start_index = date_to_index.get(cross.bar_date)
        if start_index is None:
            continue
        end_index = min(start_index + pullback_wait_days, len(closes) - 1)
        for index in range(start_index + 1, end_index + 1):
            slow_ma0 = _sma(closes, slow_window, index)
            fast_ma0 = _sma(closes, fast_window, index)
            if slow_ma0 is None or fast_ma0 is None or fast_ma0 <= slow_ma0:
                continue
            close = closes[index]
            lower = slow_ma0 * (1 - band)
            upper = slow_ma0 * (1 + band)
            if not (lower <= close <= upper):
                continue
            if not _volume_shrink_at(volumes, index):
                continue
            vol_ratio = _volume_ratio_at(volumes, index) or 0.0
            bar_dt = dates[index]
            bar_date = bar_dt.strftime("%Y-%m-%d") if isinstance(bar_dt, datetime) else bar_dt.isoformat()
            entries.append(
                PullbackEntry(
                    bar_date=bar_date,
                    close=round(close, 2),
                    fast_ma=round(fast_ma0, 2),
                    slow_ma=round(slow_ma0, 2),
                    volume_ratio=round(vol_ratio, 2),
                )
            )
            break
    return entries


def summarize_swing_ma_state(
    closes: list[float],
    dates: list[date | datetime],
    volumes: list[float],
    *,
    lows: list[float] | None = None,
    fast_window: int = 10,
    slow_window: int = 20,
    pullback_pct: float = 2.0,
    pullback_wait_days: int = 5,
    recent_limit: int = 5,
) -> dict[str, Any]:
    """汇总波段回踩状态与最近入场事件。"""
    min_bars = slow_window + 2
    if len(closes) < min_bars:
        return {
            "error": "K 线数量不足，无法计算波段回踩信号",
            "min_bars": min_bars,
            "bars_available": len(closes),
        }

    ma_state = summarize_double_ma_state(
        closes,
        dates,
        fast_window=fast_window,
        slow_window=slow_window,
        recent_limit=recent_limit,
    )
    low_series = lows if lows is not None else closes
    entries = compute_swing_pullback_entries(
        closes,
        low_series,
        dates,
        volumes,
        fast_window=fast_window,
        slow_window=slow_window,
        pullback_pct=pullback_pct,
        pullback_wait_days=pullback_wait_days,
    )
    last_entry = entries[-1] if entries else None
    last_entry_payload: dict[str, Any] | None = None
    if last_entry is not None:
        last_entry_payload = {
            "type": "pullback_entry",
            "type_label": "缩量回踩",
            "date": last_entry.bar_date,
            "close": last_entry.close,
            "fast_ma": last_entry.fast_ma,
            "slow_ma": last_entry.slow_ma,
            "volume_ratio": last_entry.volume_ratio,
        }

    return {
        **ma_state,
        "params": {
            "fast_window": fast_window,
            "slow_window": slow_window,
            "pullback_pct": pullback_pct,
            "pullback_wait_days": pullback_wait_days,
        },
        "last_entry": last_entry_payload,
        "recent_entries": [
            {
                "type": "pullback_entry",
                "type_label": "缩量回踩",
                "date": item.bar_date,
                "close": item.close,
                "volume_ratio": item.volume_ratio,
            }
            for item in entries[-recent_limit:]
        ],
        "entry_count": len(entries),
    }


def classify_swing_ma_signal(
    state: dict[str, Any],
    *,
    recent_days: int = 5,
) -> Literal["buy", "sell", "hold", "na"]:
    """波段回踩信号（回踩买 / 死叉卖）。"""
    if state.get("error"):
        return "na"

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    if fast_ma is None or slow_ma is None:
        return "na"

    as_of = str(state.get("as_of") or "")
    last_cross = state.get("last_cross")
    if last_cross and as_of:
        cross_date = str(last_cross.get("date") or "")
        elapsed = _days_between(as_of, cross_date)
        if elapsed is not None and elapsed <= max(0, int(recent_days)) and last_cross.get("type") == "death_cross" and fast_ma < slow_ma:
            return "sell"

    last_entry = state.get("last_entry")
    if not last_entry or not as_of:
        return "hold"

    elapsed = _days_between(as_of, str(last_entry.get("date") or ""))
    if elapsed is None or elapsed > max(0, int(recent_days)):
        return "hold"

    if fast_ma > slow_ma:
        return "buy"
    return "hold"


def build_swing_ma_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareSwingMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
    pullback_pct: float = 2.0,
    pullback_wait_days: int = 5,
    recent_days: int = 5,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> dict[str, Any]:
    """波段回踩均线信号快照。"""
    high_series = highs if highs is not None else closes
    low_series = lows if lows is not None else closes
    vol_series = volumes if volumes is not None else []

    if not vol_series:
        warnings = ["缺少成交量序列，无法计算波段回踩信号"]
        return {
            "vt_symbol": vt_symbol,
            "strategy_id": strategy_id,
            "as_of": "",
            "signal": "na",
            "signal_label": "—",
            "signal_date": None,
            "ref_buy_price": None,
            "ref_sell_price": None,
            "action_ref_buy_price": None,
            "action_ref_sell_price": None,
            "strength": None,
            "reason_summary": "",
            "reasons": (),
            "warnings": tuple(warnings),
            "last_close": None,
        }

    state = summarize_swing_ma_state(
        closes,
        dates,
        vol_series,
        lows=low_series,
        fast_window=fast_window,
        slow_window=slow_window,
        pullback_pct=pullback_pct,
        pullback_wait_days=pullback_wait_days,
    )
    warnings: list[str] = []
    if state.get("error"):
        warnings.append(str(state["error"]))
        return {
            "vt_symbol": vt_symbol,
            "strategy_id": strategy_id,
            "as_of": "",
            "signal": "na",
            "signal_label": "—",
            "signal_date": None,
            "ref_buy_price": None,
            "ref_sell_price": None,
            "action_ref_buy_price": None,
            "action_ref_sell_price": None,
            "strength": None,
            "reason_summary": "",
            "reasons": (),
            "warnings": tuple(warnings),
            "last_close": None,
        }

    last_close = round(closes[-1], 2)
    ma5 = _sma_at(closes, 5)
    ma10 = _sma_at(closes, 10)
    ma20 = _sma_at(closes, 20)
    volume_ratio = _volume_ratio_5d(vol_series)

    signal = classify_swing_ma_signal(state, recent_days=recent_days)
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
    last_entry = state.get("last_entry") or {}
    last_cross = state.get("last_cross") or {}
    signal_date = None
    if signal == "buy":
        signal_date = last_entry.get("date")
    elif signal == "sell":
        signal_date = last_cross.get("date")

    ref_buy, ref_sell = _compute_ref_prices(
        state,
        high_series,
        signal=signal,
        fast_window=fast_window,
        slow_window=slow_window,
    )
    action_buy, action_sell = _compute_action_ref_prices(
        state,
        high_series,
        low_series,
        signal=signal,
        last_close=last_close,
        fast_window=fast_window,
        slow_window=slow_window,
    )

    pattern_hit = _is_ma_bull_pattern(closes)
    align_score = _alignment_score(ma5=ma5, ma10=ma10, ma20=ma20, last_close=last_close)
    vol_score = _volume_score(volume_ratio)
    pat_score = 90.0 if pattern_hit else 30.0
    cross_score = _ma_signal_score(signal)
    strength = _compute_strength(
        signal=signal,
        alignment=align_score,
        volume=vol_score,
        pattern=pat_score,
    )

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    ma_gap_pct: float | None = None
    if isinstance(fast_ma, (int, float)) and isinstance(slow_ma, (int, float)) and float(slow_ma) > 0:
        ma_gap_pct = round((float(fast_ma) - float(slow_ma)) / float(slow_ma) * 100, 2)

    tags: list[str] = []
    if last_entry.get("type_label"):
        tags.append(str(last_entry["type_label"]))
    if last_cross.get("type_label"):
        tags.append(str(last_cross["type_label"]))
    if volume_ratio is not None:
        tags.append(f"量比{volume_ratio:.1f}")
    reason_summary = "+".join(tags) if tags else labels[signal]

    reasons: list[str] = []
    alignment = current.get("alignment")
    if alignment:
        reasons.append(str(alignment))
    if last_entry.get("type_label") and last_entry.get("date"):
        reasons.append(f"最近回踩：{last_entry['type_label']}（{last_entry['date']}） 量比 {last_entry.get('volume_ratio', '—')}")
    if last_cross.get("type_label") and last_cross.get("date"):
        reasons.append(f"最近交叉：{last_cross['type_label']}（{last_cross['date']}）")
    reasons.append(f"综合：{reason_summary}")
    reasons.extend(
        _ref_price_reason_lines(
            signal=signal,
            ref_buy=ref_buy,
            ref_sell=ref_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.extend(
        _action_ref_reason_lines(
            signal=signal,
            action_buy=action_buy,
            action_sell=action_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.append(f"强度：{strength:.0f}")

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": str(state.get("as_of") or ""),
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": signal_date,
        "ref_buy_price": ref_buy,
        "ref_sell_price": ref_sell,
        "action_ref_buy_price": action_buy,
        "action_ref_sell_price": action_sell,
        "strength": strength,
        "reason_summary": reason_summary,
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": last_close,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "volume_ratio_5d": volume_ratio,
        "ma_gap_pct": ma_gap_pct,
        "strength_cross": cross_score,
        "strength_alignment": align_score,
        "strength_volume": vol_score,
        "strength_pattern": pat_score,
    }


def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """Wilder 平滑序列。"""
    if len(values) < period:
        return [None] * len(values)
    result: list[float | None] = [None] * len(values)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    prev = seed
    for index in range(period, len(values)):
        prev = (prev * (period - 1) + values[index]) / period
        result[index] = prev
    return result


def _compute_adx_at(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    end_index: int,
    *,
    period: int = 14,
) -> float | None:
    """单点 ADX（与 vnpy ArrayManager.adx 算法一致）。"""
    if end_index + 1 < period * 2:
        return None
    segment_highs = highs[: end_index + 1]
    segment_lows = lows[: end_index + 1]
    segment_closes = closes[: end_index + 1]
    count = len(segment_closes)
    tr_values = [0.0] * count
    plus_dm = [0.0] * count
    minus_dm = [0.0] * count
    for index in range(1, count):
        up_move = segment_highs[index] - segment_highs[index - 1]
        down_move = segment_lows[index - 1] - segment_lows[index]
        plus_dm[index] = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm[index] = down_move if down_move > up_move and down_move > 0 else 0.0
        tr_values[index] = max(
            segment_highs[index] - segment_lows[index],
            abs(segment_highs[index] - segment_closes[index - 1]),
            abs(segment_lows[index] - segment_closes[index - 1]),
        )

    atr = _wilder_smooth(tr_values, period)
    smooth_plus = _wilder_smooth(plus_dm, period)
    smooth_minus = _wilder_smooth(minus_dm, period)
    if atr[end_index] is None or smooth_plus[end_index] is None or smooth_minus[end_index] is None:
        return None
    if atr[end_index] <= 0:
        return None

    plus_di = 100.0 * smooth_plus[end_index] / atr[end_index]
    minus_di = 100.0 * smooth_minus[end_index] / atr[end_index]
    di_sum = plus_di + minus_di
    if di_sum <= 0:
        return None

    dx_values = [0.0] * count
    for index in range(1, count):
        atr_val = atr[index]
        sp = smooth_plus[index]
        sm = smooth_minus[index]
        if atr_val is None or sp is None or sm is None or atr_val <= 0:
            continue
        pdi = 100.0 * sp / atr_val
        mdi = 100.0 * sm / atr_val
        total = pdi + mdi
        if total > 0:
            dx_values[index] = 100.0 * abs(pdi - mdi) / total

    adx_series = _wilder_smooth(dx_values, period)
    value = adx_series[end_index]
    if value is None:
        return None
    return round(float(value), 2)


def _adx_score(adx: float | None, *, threshold: float = 25.0) -> float:
    if adx is None:
        return 30.0
    if adx >= threshold + 10:
        return 90.0
    if adx >= threshold:
        return 75.0
    if adx >= threshold - 5:
        return 50.0
    return 20.0


def _trend_alignment_score(
    *,
    fast_ma: float | None,
    slow_ma: float | None,
    last_close: float,
    slow_slope: float | None,
) -> float:
    if fast_ma is None or slow_ma is None:
        return 30.0
    if fast_ma > slow_ma and last_close >= slow_ma:
        if slow_slope is not None and slow_slope > 0:
            return 95.0
        return 85.0
    if fast_ma < slow_ma and last_close < slow_ma:
        return 15.0
    return 50.0


def _trend_strength(
    *,
    signal: Literal["buy", "sell", "hold", "na"],
    alignment: float,
    adx: float,
    cross: float,
    relative_index_pct: float | None = None,
) -> float:
    rel_score = 50.0
    if relative_index_pct is not None:
        if relative_index_pct > 2:
            rel_score = 85.0
        elif relative_index_pct > 0:
            rel_score = 70.0
        elif relative_index_pct < -2:
            rel_score = 20.0
        else:
            rel_score = 45.0
    score = 0.35 * alignment + 0.25 * adx + 0.20 * rel_score + 0.20 * cross
    if signal in ("buy", "sell"):
        score = max(score, 55.0)
    return round(max(0.0, min(score, 100.0)), 1)


def summarize_trend_ma_state(
    closes: list[float],
    dates: list[date | datetime],
    highs: list[float],
    lows: list[float],
    *,
    fast_window: int = 20,
    slow_window: int = 60,
    adx_period: int = 14,
    adx_threshold: float = 25.0,
    recent_limit: int = 5,
) -> dict[str, Any]:
    """汇总趋势均线 + ADX 状态。"""
    min_bars = max(slow_window, adx_period * 2) + 2
    if len(closes) < min_bars:
        return {
            "error": "K 线数量不足，无法计算趋势信号",
            "min_bars": min_bars,
            "bars_available": len(closes),
        }

    ma_state = summarize_double_ma_state(
        closes,
        dates,
        fast_window=fast_window,
        slow_window=slow_window,
        recent_limit=recent_limit,
    )
    last_index = len(closes) - 1
    adx_value = _compute_adx_at(highs, lows, closes, last_index, period=adx_period)
    slow_ma0 = _sma(closes, slow_window, last_index)
    slow_ma1 = _sma(closes, slow_window, last_index - 1)
    slow_slope = None
    if slow_ma0 is not None and slow_ma1 is not None:
        slow_slope = round(slow_ma0 - slow_ma1, 4)

    current = dict(ma_state.get("current") or {})
    current["adx"] = adx_value
    current["slow_slope"] = slow_slope
    current["above_slow_ma"] = slow_ma0 is not None and closes[last_index] >= slow_ma0
    current["adx_pass"] = adx_value is not None and adx_value >= adx_threshold

    return {
        **ma_state,
        "params": {
            "fast_window": fast_window,
            "slow_window": slow_window,
            "adx_period": adx_period,
            "adx_threshold": adx_threshold,
        },
        "current": current,
    }


def classify_trend_ma_signal(
    state: dict[str, Any],
    *,
    recent_days: int = 15,
    adx_threshold: float = 25.0,
) -> Literal["buy", "sell", "hold", "na"]:
    """趋势均线信号（金叉+ADX 过滤买 / 死叉卖）。"""
    if state.get("error"):
        return "na"

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    adx_value = current.get("adx")
    if fast_ma is None or slow_ma is None:
        return "na"

    as_of = str(state.get("as_of") or "")
    last_cross = state.get("last_cross")
    if not last_cross or not as_of:
        return "hold"

    cross_date = str(last_cross.get("date") or "")
    elapsed = _days_between(as_of, cross_date)
    if elapsed is None or elapsed > max(0, int(recent_days)):
        return "hold"

    cross_type = last_cross.get("type")
    if cross_type == "death_cross" and fast_ma < slow_ma:
        return "sell"
    if cross_type == "golden_cross" and fast_ma > slow_ma:
        if adx_value is None or float(adx_value) < adx_threshold:
            return "hold"
        if not current.get("above_slow_ma"):
            return "hold"
        slow_slope = current.get("slow_slope")
        if slow_slope is not None and float(slow_slope) < 0:
            return "hold"
        return "buy"
    return "hold"


def build_trend_ma_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareTrendMaStrategy",
    fast_window: int = 20,
    slow_window: int = 60,
    adx_period: int = 14,
    adx_threshold: float = 25.0,
    recent_days: int = 15,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    relative_index_pct: float | None = None,
) -> dict[str, Any]:
    """趋势均线 + ADX 信号快照。"""
    high_series = highs if highs is not None else closes
    low_series = lows if lows is not None else closes
    vol_series = volumes if volumes is not None else []

    state = summarize_trend_ma_state(
        closes,
        dates,
        high_series,
        low_series,
        fast_window=fast_window,
        slow_window=slow_window,
        adx_period=adx_period,
        adx_threshold=adx_threshold,
    )
    warnings: list[str] = []
    if state.get("error"):
        warnings.append(str(state["error"]))
        return {
            "vt_symbol": vt_symbol,
            "strategy_id": strategy_id,
            "as_of": "",
            "signal": "na",
            "signal_label": "—",
            "signal_date": None,
            "ref_buy_price": None,
            "ref_sell_price": None,
            "action_ref_buy_price": None,
            "action_ref_sell_price": None,
            "strength": None,
            "reason_summary": "",
            "reasons": (),
            "warnings": tuple(warnings),
            "last_close": None,
        }

    last_close = round(closes[-1], 2)
    volume_ratio = _volume_ratio_5d(vol_series) if vol_series else None
    signal = classify_trend_ma_signal(
        state,
        recent_days=recent_days,
        adx_threshold=adx_threshold,
    )
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
    last_cross = state.get("last_cross") or {}
    signal_date = last_cross.get("date") if signal in ("buy", "sell") else None

    ref_buy, ref_sell = _compute_ref_prices(
        state,
        high_series,
        signal=signal,
        fast_window=fast_window,
        slow_window=slow_window,
        lookback_high=60,
    )
    action_buy, action_sell = _compute_action_ref_prices(
        state,
        high_series,
        low_series,
        signal=signal,
        last_close=last_close,
        fast_window=fast_window,
        slow_window=slow_window,
        lookback=60,
    )

    current = state.get("current") or {}
    fast_ma = current.get("fast_ma")
    slow_ma = current.get("slow_ma")
    adx_value = current.get("adx")
    slow_slope = current.get("slow_slope")
    ma_gap_pct: float | None = None
    if isinstance(fast_ma, (int, float)) and isinstance(slow_ma, (int, float)) and float(slow_ma) > 0:
        ma_gap_pct = round((float(fast_ma) - float(slow_ma)) / float(slow_ma) * 100, 2)

    align_score = _trend_alignment_score(
        fast_ma=fast_ma if isinstance(fast_ma, (int, float)) else None,
        slow_ma=slow_ma if isinstance(slow_ma, (int, float)) else None,
        last_close=last_close,
        slow_slope=float(slow_slope) if isinstance(slow_slope, (int, float)) else None,
    )
    adx_score = _adx_score(
        float(adx_value) if isinstance(adx_value, (int, float)) else None,
        threshold=adx_threshold,
    )
    cross_score = _ma_signal_score(signal)
    strength = _trend_strength(
        signal=signal,
        alignment=align_score,
        adx=adx_score,
        cross=cross_score,
        relative_index_pct=relative_index_pct,
    )

    tags: list[str] = []
    if last_cross.get("type_label"):
        tags.append(str(last_cross["type_label"]))
    if isinstance(adx_value, (int, float)):
        tags.append(f"ADX{float(adx_value):.0f}")
    if current.get("adx_pass"):
        tags.append("趋势")
    if relative_index_pct is not None:
        tags.append(f"超额{relative_index_pct:+.1f}%")
    reason_summary = "+".join(tags) if tags else labels[signal]

    reasons: list[str] = []
    alignment = current.get("alignment")
    if alignment:
        reasons.append(str(alignment))
    if isinstance(adx_value, (int, float)):
        reasons.append(f"ADX({adx_period}) = {float(adx_value):.1f}，阈值 {adx_threshold:.0f}")
    if last_cross.get("type_label") and last_cross.get("date"):
        reasons.append(f"最近交叉：{last_cross['type_label']}（{last_cross['date']}）")
    if isinstance(slow_slope, (int, float)):
        reasons.append(f"慢线斜率：{float(slow_slope):+.4f}")
    reasons.append(f"综合：{reason_summary}")
    reasons.extend(
        _ref_price_reason_lines(
            signal=signal,
            ref_buy=ref_buy,
            ref_sell=ref_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.extend(
        _action_ref_reason_lines(
            signal=signal,
            action_buy=action_buy,
            action_sell=action_sell,
            fast_window=fast_window,
            slow_window=slow_window,
        )
    )
    reasons.append(f"强度：{strength:.0f}")

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": str(state.get("as_of") or ""),
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": signal_date,
        "ref_buy_price": ref_buy,
        "ref_sell_price": ref_sell,
        "action_ref_buy_price": action_buy,
        "action_ref_sell_price": action_sell,
        "strength": strength,
        "reason_summary": reason_summary,
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": last_close,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "volume_ratio_5d": volume_ratio,
        "ma_gap_pct": ma_gap_pct,
        "strength_cross": cross_score,
        "strength_alignment": align_score,
        "strength_volume": adx_score,
        "strength_pattern": None,
    }


def build_signal_payload_for_strategy(
    strategy_id: str,
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    fast_window: int,
    slow_window: int,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    relative_index_pct: float | None = None,
) -> dict[str, Any] | None:
    """按策略 ID 构建信号快照 payload。"""
    kind = SUPPORTED_SIGNAL_STRATEGIES.get(strategy_id)
    recent_days = STRATEGY_SIGNAL_RECENT_DAYS.get(strategy_id, 5)
    if kind == "double_ma":
        return build_double_ma_signal_payload(
            closes,
            dates,
            vt_symbol=vt_symbol,
            strategy_id=strategy_id,
            fast_window=fast_window,
            slow_window=slow_window,
            recent_days=recent_days,
            highs=highs,
            lows=lows,
            volumes=volumes,
        )
    if kind == "short_breakout":
        return build_short_breakout_signal_payload(
            closes,
            dates,
            vt_symbol=vt_symbol,
            strategy_id=strategy_id,
            fast_window=fast_window,
            slow_window=slow_window,
            recent_days=recent_days,
            highs=highs,
            lows=lows,
            volumes=volumes,
        )
    if kind == "swing_ma":
        return build_swing_ma_signal_payload(
            closes,
            dates,
            vt_symbol=vt_symbol,
            strategy_id=strategy_id,
            fast_window=fast_window,
            slow_window=slow_window,
            recent_days=recent_days,
            highs=highs,
            lows=lows,
            volumes=volumes,
        )
    if kind == "trend_ma":
        return build_trend_ma_signal_payload(
            closes,
            dates,
            vt_symbol=vt_symbol,
            strategy_id=strategy_id,
            fast_window=fast_window,
            slow_window=slow_window,
            recent_days=recent_days,
            highs=highs,
            lows=lows,
            volumes=volumes,
            relative_index_pct=relative_index_pct,
        )
    if kind == "limit_board":
        from strategies.ultra_short_signals import build_limit_board_signal_payload

        return build_limit_board_signal_payload(
            closes,
            dates,
            vt_symbol=vt_symbol,
            strategy_id=strategy_id,
            highs=highs,
            volumes=volumes,
            recent_days=recent_days,
        )
    if kind == "intraday_breakout":
        from strategies.ultra_short_signals import build_intraday_breakout_signal_payload

        return build_intraday_breakout_signal_payload(
            closes,
            dates,
            vt_symbol=vt_symbol,
            strategy_id=strategy_id,
            highs=highs,
            volumes=volumes,
            recent_days=recent_days,
        )
    if kind == "pullback":
        from strategies.ultra_short_signals import build_pullback_signal_payload

        return build_pullback_signal_payload(
            closes,
            dates,
            vt_symbol=vt_symbol,
            strategy_id=strategy_id,
            highs=highs,
            volumes=volumes,
            recent_days=recent_days,
        )
    return None
