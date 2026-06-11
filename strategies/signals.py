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
            lines.append(
                f"参考买价：min(金叉/慢{slow_window}/收盘) 低吸入场 = {action_buy}"
            )
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
    if (
        isinstance(fast_ma, (int, float))
        and isinstance(slow_ma, (int, float))
        and float(slow_ma) > 0
    ):
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
