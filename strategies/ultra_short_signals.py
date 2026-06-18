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
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    recent_days: int = 1,
    first_time: str = "",
    reject_one_word: bool = True,
) -> dict[str, Any]:
    """打板信号快照（日 K 涨停 + 封板代理；封板时间来自 limit_list_d）。"""
    symbol = vt_symbol.split(".", 1)[0]
    high_series = highs if highs is not None else closes
    low_series = lows if lows is not None else closes
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

    one_word = False
    if reject_one_word and lows is not None and limit_up_today and last_close > 0:
        bar_high = high_series[last_index]
        bar_low = low_series[last_index]
        amplitude = (bar_high - bar_low) / last_close * 100
        one_word = amplitude >= 0 and amplitude < 0.5

    resolved_first_time = (first_time or "").strip()
    intraday_snapshot = None
    if limit_up_today or not resolved_first_time:
        from datetime import datetime as dt

        from vnpy_ashare.trading.signals.limit_board_intraday import evaluate_limit_board_from_local_minutes

        end_d = dates[last_index]
        trade_date = end_d.date() if isinstance(end_d, dt) else end_d
        intraday_snapshot = evaluate_limit_board_from_local_minutes(
            vt_symbol,
            trade_date,
            reject_one_word=reject_one_word,
        )

    if intraday_snapshot is not None:
        if intraday_snapshot.first_time:
            resolved_first_time = intraday_snapshot.first_time
        if intraday_snapshot.eligible:
            limit_up_today = True
            one_word = intraday_snapshot.one_word
        elif intraday_snapshot.first_time and reject_one_word and intraday_snapshot.one_word:
            limit_up_today = False
            one_word = True

    if not resolved_first_time and limit_up_today:
        from vnpy_ashare.trading.signals.intraday_seal_time import resolve_first_time

        resolved_first_time = resolve_first_time(vt_symbol, prev_close=prev_close)

    from vnpy_ashare.trading.signals.seal_time import format_seal_time_label, seal_time_score

    seal_score = seal_time_score(resolved_first_time)
    seal_label = format_seal_time_label(resolved_first_time)

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
        limit_up_today=limit_up_today and not one_word,
        recent_days=recent_days,
        days_since_event=days_since,
    )
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}

    threshold = limit_board_threshold_pct({"symbol": symbol})
    change_pct = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0

    reasons: list[str] = []
    if intraday_snapshot is not None and intraday_snapshot.first_time:
        reasons.extend(intraday_snapshot.reasons)
        reasons.append(f"涨停价参考 {limit_price:.2f}")
    elif one_word:
        reasons.append("近似一字板，打板回避")
    elif limit_up_today:
        reasons.append(f"涨停封板代理：涨幅 {change_pct:.1f}%（阈值 {threshold:.1f}%）")
        reasons.append(f"涨停价参考 {limit_price:.2f}")
        if seal_label:
            reasons.append(f"封板时间 {seal_label}（得分 {seal_score:.1f}）")
    elif last_event_index is not None and days_since is not None and days_since <= recent_days:
        reasons.append(f"近 {recent_days} 日有涨停：{signal_date}")
    else:
        reasons.append("未触及涨停价/封板条件")

    if seal_score <= 0 and limit_up_today and not one_word:
        warnings.append("封板时间缺失，封板质量降权")
    if intraday_snapshot is not None:
        warnings.extend(intraday_snapshot.warnings)
    else:
        warnings.append("日 K 代理规则；完整分 K 打板须结合 TickFlow 或本地 1m")

    base_strength = 85.0 if limit_up_today and not one_word else 45.0 if days_since is not None and days_since <= recent_days else 30.0
    strength = round(min(100.0, base_strength + seal_score * 10.0), 1)

    fast_ma = _sma(closes, 5)
    slow_ma = _sma(closes, 10)
    recent_limit = limit_up_today or (days_since is not None and days_since <= recent_days)
    struct_buy = limit_price if recent_limit else slow_ma
    struct_sell = last_close if signal == "buy" else (fast_ma if fast_ma is not None else last_close)
    action_buy = limit_price if limit_up_today else (struct_buy if struct_buy is not None else last_close)
    action_sell = last_close

    payload = {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": as_of,
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": signal_date,
        "ref_buy_price": round(struct_buy, 2) if struct_buy is not None else None,
        "ref_sell_price": round(struct_sell, 2) if struct_sell is not None else None,
        "action_ref_buy_price": round(action_buy, 2) if action_buy is not None else None,
        "action_ref_sell_price": action_sell,
        "strength": strength,
        "reason_summary": "涨停" if limit_up_today else "打板观望",
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": last_close,
        "limit_price": limit_price,
        "change_pct": round(change_pct, 2),
        "first_time": resolved_first_time or None,
        "seal_time_label": seal_label or None,
        "seal_time_score": seal_score,
        "fast_ma": round(fast_ma, 2) if fast_ma is not None else None,
        "slow_ma": round(slow_ma, 2) if slow_ma is not None else None,
    }
    return _append_technical_fields(payload, closes, volumes)


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


def _append_technical_fields(
    payload: dict[str, Any],
    closes: list[float],
    volumes: list[float] | None,
    *,
    fast_window: int = 5,
    slow_window: int = 10,
) -> dict[str, Any]:
    """补全信号区通用列：量比、快慢均线、快慢距。"""
    if not closes:
        return payload
    last_index = len(closes) - 1
    fast_ma = _sma(closes, fast_window)
    slow_ma = _sma(closes, slow_window)
    vol_ratio = _volume_ratio_at(volumes, last_index) if volumes else None
    gap: float | None = None
    if fast_ma is not None and slow_ma is not None and slow_ma > 0:
        gap = round((fast_ma - slow_ma) / slow_ma * 100, 2)
    merged = dict(payload)
    if merged.get("fast_ma") is None and fast_ma is not None:
        merged["fast_ma"] = round(fast_ma, 2)
    if merged.get("slow_ma") is None and slow_ma is not None:
        merged["slow_ma"] = round(slow_ma, 2)
    if merged.get("volume_ratio_5d") is None and vol_ratio is not None:
        merged["volume_ratio_5d"] = round(vol_ratio, 2)
    if merged.get("ma_gap_pct") is None and gap is not None:
        merged["ma_gap_pct"] = gap
    if merged.get("strength_volume") is None and vol_ratio is not None:
        merged["strength_volume"] = round(min(100.0, max(0.0, vol_ratio * 50.0)), 1)
    return merged


def classify_intraday_breakout_bar(
    closes: list[float],
    highs: list[float],
    volumes: list[float],
    index: int,
    *,
    symbol: str,
    min_change_pct: float = 3.0,
    max_change_pct: float = 7.0,
    volume_ratio_min: float = 1.2,
) -> tuple[SignalKind, float]:
    """半路买入判定（日 K 代理）；返回 (signal, change_pct)。"""
    if index < 1:
        return "hold", 0.0
    prev_close = closes[index - 1]
    if prev_close <= 0:
        return "hold", 0.0
    last_close = closes[index]
    change_pct = (last_close - prev_close) / prev_close * 100
    row = {"symbol": symbol, "change_pct": change_pct}
    at_limit = is_at_limit_board(row)
    in_band = min_change_pct <= change_pct <= max_change_pct and not at_limit
    vol_ratio = _volume_ratio_at(volumes, index) if volumes else None
    volume_ok = vol_ratio is None or vol_ratio >= volume_ratio_min
    if in_band and volume_ok:
        return "buy", change_pct
    return "hold", change_pct


def classify_pullback_bar(
    closes: list[float],
    volumes: list[float],
    index: int,
    *,
    ma_window: int = 5,
    pullback_band_pct: float = 2.0,
) -> SignalKind:
    """低吸买入判定（日 K 代理）。"""
    if index + 1 < ma_window + 1:
        return "hold"
    ma5 = _sma(closes[: index + 1], ma_window)
    ma10 = _sma(closes[: index + 1], 10)
    if ma5 is None:
        return "hold"
    last_close = closes[index]
    band = pullback_band_pct / 100.0
    near_ma5 = abs(last_close - ma5) / ma5 <= band if ma5 > 0 else False
    trend_ok = ma10 is not None and ma5 >= ma10 * 0.995
    vol_shrink = True
    if volumes and index >= 5:
        base = sum(volumes[index - 5 : index]) / 5
        vol_shrink = volumes[index] <= base if base > 0 else True
    return "buy" if near_ma5 and trend_ok and vol_shrink else "hold"


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
    warn_list: list[str] = []
    if len(closes) < 3:
        return _empty_payload(vt_symbol, strategy_id, warnings=("K 线数量不足",))

    last_index = len(closes) - 1
    as_of = _bar_date_text(dates[last_index])
    last_close = round(closes[last_index], 2)
    prev_close = closes[last_index - 1]
    change_pct = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
    vol_ratio = _volume_ratio_at(vol_series, last_index) if vol_series else None

    intraday_snapshot = None
    from datetime import datetime as dt

    from vnpy_ashare.trading.signals.intraday_breakout_intraday import evaluate_intraday_breakout_from_local_minutes

    end_d = dates[last_index]
    trade_date = end_d.date() if isinstance(end_d, dt) else end_d
    intraday_snapshot = evaluate_intraday_breakout_from_local_minutes(
        vt_symbol,
        trade_date,
        min_change_pct=min_change_pct,
        max_change_pct=max_change_pct,
        volume_ratio_min=volume_ratio_min,
    )

    signal, change_pct = classify_intraday_breakout_bar(
        closes,
        high_series,
        vol_series,
        last_index,
        symbol=symbol,
        min_change_pct=min_change_pct,
        max_change_pct=max_change_pct,
        volume_ratio_min=volume_ratio_min,
    )
    if intraday_snapshot is not None:
        signal = "buy" if intraday_snapshot.eligible else "hold"
        change_pct = intraday_snapshot.change_pct
        if intraday_snapshot.volume_ratio is not None:
            vol_ratio = intraday_snapshot.volume_ratio
    row = {"symbol": symbol, "change_pct": change_pct}
    at_limit = is_at_limit_board(row)
    if change_pct > max_change_pct and not at_limit and intraday_snapshot is None:
        warn_list.append("涨幅已超半路上限，更宜打板或观望")

    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
    if intraday_snapshot is not None and intraday_snapshot.breakout_level > 0:
        breakout_level = intraday_snapshot.breakout_level
    else:
        breakout_level = max(high_series[max(0, last_index - 5) : last_index]) if last_index > 0 else last_close
    slow_ma = _sma(closes, 10)
    ref_buy = round(breakout_level, 2) if signal == "buy" else (round(slow_ma, 2) if slow_ma is not None else None)
    fast_ma = _sma(closes, 5)
    struct_sell = round(fast_ma, 2) if fast_ma is not None else last_close

    reasons: list[str] = []
    if intraday_snapshot is not None and intraday_snapshot.reasons:
        reasons.extend(intraday_snapshot.reasons)
    else:
        reasons.append(f"涨幅 {change_pct:.1f}%（半路区间 {min_change_pct:.0f}–{max_change_pct:.0f}%）")
        if vol_ratio is not None:
            reasons.append(f"量比 {vol_ratio:.1f}")
    strength = 75.0 if signal == "buy" else 35.0

    if intraday_snapshot is not None:
        warn_list = list(intraday_snapshot.warnings)
    else:
        warn_list = ["日 K 代理，非分 K 半路；完整规则须本地 1m 或 TickFlow"]
    if change_pct > max_change_pct and not at_limit:
        warn_list.append("涨幅已超半路上限，更宜打板或观望")

    payload = {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": as_of,
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": as_of if signal == "buy" else None,
        "ref_buy_price": ref_buy,
        "ref_sell_price": struct_sell,
        "action_ref_buy_price": ref_buy or last_close,
        "action_ref_sell_price": last_close,
        "strength": strength,
        "reason_summary": "半路" if signal == "buy" else "半路观望",
        "reasons": tuple(reasons),
        "warnings": tuple(warn_list),
        "last_close": last_close,
        "change_pct": round(change_pct, 2),
        "volume_ratio_5d": round(vol_ratio, 2) if vol_ratio is not None else None,
    }
    return _append_technical_fields(payload, closes, vol_series or None)


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
    warn_list: list[str] = []
    if len(closes) < ma_window + 2:
        return _empty_payload(vt_symbol, strategy_id, warnings=("K 线数量不足",))

    last_index = len(closes) - 1
    as_of = _bar_date_text(dates[last_index])
    last_close = round(closes[last_index], 2)
    ma5 = _sma(closes, ma_window)
    ma10 = _sma(closes, 10)
    if ma5 is None:
        return _empty_payload(vt_symbol, strategy_id, warnings=("均线不足",))

    intraday_snapshot = None
    from datetime import datetime as dt

    from vnpy_ashare.trading.signals.pullback_intraday import evaluate_pullback_from_local_minutes

    end_d = dates[last_index]
    trade_date = end_d.date() if isinstance(end_d, dt) else end_d
    intraday_snapshot = evaluate_pullback_from_local_minutes(
        vt_symbol,
        trade_date,
        ma_window=ma_window,
        pullback_band_pct=pullback_band_pct,
    )

    signal = classify_pullback_bar(
        closes,
        vol_series,
        last_index,
        ma_window=ma_window,
        pullback_band_pct=pullback_band_pct,
    )
    if intraday_snapshot is not None:
        signal = "buy" if intraday_snapshot.eligible else "hold"
        if intraday_snapshot.daily_ma5 > 0:
            ma5 = intraday_snapshot.daily_ma5
    vol_shrink = True
    if vol_series and last_index >= 5:
        base = sum(vol_series[last_index - 5 : last_index]) / 5
        vol_shrink = vol_series[last_index] <= base if base > 0 else True
    if intraday_snapshot is not None:
        vol_shrink = intraday_snapshot.volume_shrink
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
    ref_buy = round(ma5, 2) if signal == "buy" else None
    reasons: list[str] = []
    if intraday_snapshot is not None and intraday_snapshot.reasons:
        reasons.extend(intraday_snapshot.reasons)
    else:
        reasons = [
            f"MA{ma_window}={ma5:.2f}，现价 {last_close:.2f}",
            "缩量回踩" if vol_shrink else "量能未缩",
        ]
    strength = 70.0 if signal == "buy" else 30.0

    if intraday_snapshot is not None:
        warn_list = list(intraday_snapshot.warnings)
    else:
        warn_list = ["日 K 代理，非分时承接；完整规则须本地 1m 或 TickFlow"]

    payload = {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": as_of,
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": as_of if signal == "buy" else None,
        "ref_buy_price": ref_buy if ref_buy is not None else round(ma5, 2),
        "ref_sell_price": round(ma10, 2) if ma10 is not None else last_close,
        "action_ref_buy_price": ref_buy or last_close,
        "action_ref_sell_price": last_close,
        "strength": strength,
        "reason_summary": "低吸" if signal == "buy" else "低吸观望",
        "reasons": tuple(reasons),
        "warnings": tuple(warn_list),
        "last_close": last_close,
        "fast_ma": round(ma5, 2),
        "slow_ma": round(ma10, 2) if ma10 is not None else None,
    }
    return _append_technical_fields(payload, closes, vol_series or None, fast_window=ma_window, slow_window=10)


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
