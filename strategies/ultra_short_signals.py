"""极致短线信号：打板（日 K / 行情代理）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from vnpy_ashare.screener.hard_filters import is_at_limit_board, limit_board_threshold_pct

SignalKind = Literal["buy", "sell", "hold", "na"]


def calc_limit_price(prev_close: float, *, symbol: str) -> float:
    if prev_close <= 0:
        return 0.0
    threshold = 0.20 if symbol.startswith(("300", "688")) else 0.10
    return round(prev_close * (1 + threshold), 2)


def _bar_date_text(bar_dt: date | datetime) -> str:
    return bar_dt.strftime("%Y-%m-%d") if isinstance(bar_dt, datetime) else bar_dt.isoformat()


def _limit_up_bar(
    closes: list[float],
    highs: list[float],
    dates: list[date | datetime],
    index: int,
    *,
    symbol: str,
) -> bool:
    if index < 1:
        return False
    prev_close = closes[index - 1]
    if prev_close <= 0:
        return False
    change_pct = (closes[index] - prev_close) / prev_close * 100
    row = {
        "symbol": symbol,
        "change_pct": change_pct,
        "last_price": closes[index],
        "close": closes[index],
    }
    if not is_at_limit_board(row):
        return False
    return highs[index] > 0 and closes[index] >= highs[index] * 0.998


def classify_limit_board_signal(
    *,
    limit_up_today: bool,
    recent_days: int = 1,
    days_since_event: int | None,
) -> SignalKind:
    if limit_up_today:
        return "buy"
    if days_since_event is not None and days_since_event <= recent_days:
        return "hold"
    return "hold"


def build_limit_board_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareLimitBoardStrategy",
    highs: list[float] | None = None,
    volumes: list[float] | None = None,
    recent_days: int = 1,
) -> dict[str, Any]:
    """打板信号快照（日 K 涨停 + 封板代理；完整分 K 规则 Phase 5）。"""
    symbol = vt_symbol.split(".", 1)[0]
    high_series = highs if highs is not None else closes
    warnings: list[str] = []
    if len(closes) < 3:
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
            "warnings": ("K 线数量不足",),
            "last_close": None,
        }

    last_index = len(closes) - 1
    as_of = _bar_date_text(dates[last_index])
    last_close = round(closes[last_index], 2)
    prev_close = closes[last_index - 1]
    limit_price = calc_limit_price(prev_close, symbol=symbol)
    limit_up_today = _limit_up_bar(closes, high_series, dates, last_index, symbol=symbol)

    last_event_index: int | None = None
    for index in range(last_index, 0, -1):
        if _limit_up_bar(closes, high_series, dates, index, symbol=symbol):
            last_event_index = index
            break

    days_since: int | None = None
    signal_date: str | None = None
    if last_event_index is not None:
        signal_date = _bar_date_text(dates[last_event_index])
        end = dates[last_index]
        start = dates[last_event_index]
        end_d = end.date() if isinstance(end, datetime) else end
        start_d = start.date() if isinstance(start, datetime) else start
        days_since = (end_d - start_d).days

    signal = classify_limit_board_signal(
        limit_up_today=limit_up_today,
        recent_days=recent_days,
        days_since_event=days_since,
    )
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}

    threshold = limit_board_threshold_pct({"symbol": symbol})
    change_pct = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0

    reasons: list[str] = []
    if limit_up_today:
        reasons.append(f"涨停封板代理：涨幅 {change_pct:.1f}%（阈值 {threshold:.1f}%）")
        reasons.append(f"涨停价参考 {limit_price:.2f}")
    elif last_event_index is not None and days_since is not None and days_since <= recent_days:
        reasons.append(f"近 {recent_days} 日有涨停：{signal_date}")
    else:
        reasons.append("未触及涨停价/封板条件")

    warnings.append("日 K 代理规则，非分 K 打板；须结合情绪周期与龙头地位")

    strength = 85.0 if limit_up_today else 45.0 if days_since is not None and days_since <= recent_days else 30.0

    ref_buy = limit_price if limit_up_today or (days_since is not None and days_since <= recent_days) else None
    ref_sell = last_close if signal == "buy" else None
    action_buy = limit_price if limit_up_today else ref_buy
    action_sell = last_close

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": as_of,
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": signal_date if signal == "buy" else None,
        "ref_buy_price": ref_buy,
        "ref_sell_price": ref_sell,
        "action_ref_buy_price": action_buy,
        "action_ref_sell_price": action_sell,
        "strength": strength,
        "reason_summary": "涨停" if limit_up_today else "打板观望",
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": last_close,
        "limit_price": limit_price,
        "change_pct": round(change_pct, 2),
    }


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


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


def build_intraday_breakout_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareIntradayBreakoutStrategy",
    highs: list[float] | None = None,
    volumes: list[float] | None = None,
    min_change_pct: float = 3.0,
    max_change_pct: float = 7.0,
    volume_ratio_min: float = 1.2,
    recent_days: int = 1,
) -> dict[str, Any]:
    """半路信号（日 K 代理：涨幅 3–7% + 放量）。"""
    symbol = vt_symbol.split(".", 1)[0]
    high_series = highs if highs is not None else closes
    vol_series = volumes or []
    warn_list = ["日 K 代理，非分 K 半路；完整规则 Phase 5"]
    if len(closes) < 3:
        return _empty_payload(vt_symbol, strategy_id, warnings=("K 线数量不足",))

    last_index = len(closes) - 1
    as_of = _bar_date_text(dates[last_index])
    last_close = round(closes[last_index], 2)
    prev_close = closes[last_index - 1]
    change_pct = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
    vol_ratio = _volume_ratio_at(vol_series, last_index) if vol_series else None

    row = {"symbol": symbol, "change_pct": change_pct}
    at_limit = is_at_limit_board(row)

    in_band = min_change_pct <= change_pct <= max_change_pct and not at_limit
    volume_ok = vol_ratio is None or vol_ratio >= volume_ratio_min
    signal: SignalKind = "buy" if in_band and volume_ok else "hold"
    if change_pct > max_change_pct and not at_limit:
        warn_list.append("涨幅已超半路上限，更宜打板或观望")

    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
    breakout_level = max(high_series[max(0, last_index - 5) : last_index]) if last_index > 0 else last_close
    ref_buy = round(breakout_level, 2) if signal == "buy" else None

    reasons = [
        f"涨幅 {change_pct:.1f}%（半路区间 {min_change_pct:.0f}–{max_change_pct:.0f}%）",
    ]
    if vol_ratio is not None:
        reasons.append(f"量比 {vol_ratio:.1f}")
    strength = 75.0 if signal == "buy" else 35.0

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": as_of,
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": as_of if signal == "buy" else None,
        "ref_buy_price": ref_buy,
        "ref_sell_price": last_close,
        "action_ref_buy_price": ref_buy or last_close,
        "action_ref_sell_price": last_close,
        "strength": strength,
        "reason_summary": "半路" if signal == "buy" else "半路观望",
        "reasons": tuple(reasons),
        "warnings": tuple(warn_list),
        "last_close": last_close,
        "change_pct": round(change_pct, 2),
    }


def build_pullback_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AsharePullbackStrategy",
    highs: list[float] | None = None,
    volumes: list[float] | None = None,
    ma_window: int = 5,
    pullback_band_pct: float = 2.0,
    recent_days: int = 2,
) -> dict[str, Any]:
    """低吸信号（日 K 代理：回踩 MA5 + 缩量）。"""
    vol_series = volumes or []
    warnings = ["日 K 代理，非分时承接；须结合情绪分歧期"]
    if len(closes) < ma_window + 2:
        return _empty_payload(vt_symbol, strategy_id, warnings=("K 线数量不足",))

    last_index = len(closes) - 1
    as_of = _bar_date_text(dates[last_index])
    last_close = round(closes[last_index], 2)
    ma5 = _sma(closes, ma_window)
    ma10 = _sma(closes, 10)
    if ma5 is None:
        return _empty_payload(vt_symbol, strategy_id, warnings=("均线不足",))

    band = pullback_band_pct / 100.0
    near_ma5 = abs(last_close - ma5) / ma5 <= band if ma5 > 0 else False
    trend_ok = ma10 is not None and ma5 >= ma10 * 0.995
    vol_shrink = True
    if vol_series and last_index >= 5:
        base = sum(vol_series[last_index - 5 : last_index]) / 5
        vol_shrink = vol_series[last_index] <= base if base > 0 else True

    signal: SignalKind = "buy" if near_ma5 and trend_ok and vol_shrink else "hold"
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
    ref_buy = round(ma5, 2) if signal == "buy" else None
    reasons = [
        f"MA{ma_window}={ma5:.2f}，现价 {last_close:.2f}",
        "缩量回踩" if vol_shrink else "量能未缩",
    ]
    strength = 70.0 if signal == "buy" else 30.0

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": as_of,
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": as_of if signal == "buy" else None,
        "ref_buy_price": ref_buy,
        "ref_sell_price": last_close,
        "action_ref_buy_price": ref_buy or last_close,
        "action_ref_sell_price": last_close,
        "strength": strength,
        "reason_summary": "低吸" if signal == "buy" else "低吸观望",
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": last_close,
        "fast_ma": round(ma5, 2),
        "slow_ma": round(ma10, 2) if ma10 is not None else None,
    }


def _empty_payload(vt_symbol: str, strategy_id: str, *, warnings: tuple[str, ...]) -> dict[str, Any]:
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
        "warnings": warnings,
        "last_close": None,
    }
